from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .paths import ROOT, WORKSPACE
from .strict_verification import compare_pyc_strict
from .toolchain import compile_with_toolchain
from .upstream import CompileError, PYCFile


SESSIONS = WORKSPACE / "sessions"
EXPORTS = WORKSPACE / "exports"
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_PYC_BYTES = 64 * 1024 * 1024
SESSION_RE = re.compile(r"^ses_[0-9a-f]{16}$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def normalize_source(text: str) -> str:
    """Use LF consistently so file bytes and reported hashes agree on Windows."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # Keep the on-disk bytes identical to sha256_text(): Python's default
    # newline translation would write CRLF on Windows and break audit hashes.
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def atomic_write_json(path: Path, data: dict) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _session_dir(session_id: str) -> Path:
    if not SESSION_RE.match(session_id):
        raise ValueError("invalid session_id")
    path = SESSIONS / session_id
    if not path.is_dir():
        raise FileNotFoundError(f"session not found: {session_id}")
    return path


def _revision_dir(session_id: str, revision: int) -> Path:
    return _session_dir(session_id) / "revisions" / f"{revision:04d}"


def _read_meta(session_id: str) -> dict:
    return read_json(_session_dir(session_id) / "session.json")


def _write_meta(session_id: str, meta: dict) -> None:
    atomic_write_json(_session_dir(session_id) / "session.json", meta)


def _current_revision(meta: dict) -> int:
    return int(meta["current_revision"])


def _source_for(session_id: str, revision: int | None = None) -> tuple[int, str]:
    meta = _read_meta(session_id)
    revision = _current_revision(meta) if revision is None else int(revision)
    path = _revision_dir(session_id, revision) / "source.py"
    if not path.exists():
        raise FileNotFoundError(f"revision {revision} not found")
    return revision, path.read_text(encoding="utf-8")


def _report_for(session_id: str, revision: int | None = None) -> tuple[int, dict]:
    meta = _read_meta(session_id)
    revision = _current_revision(meta) if revision is None else int(revision)
    path = _revision_dir(session_id, revision) / "report.json"
    if not path.exists():
        raise FileNotFoundError(f"revision {revision} not found")
    return revision, read_json(path)


def _make_report(
    results,
    version: str,
    source: str,
    original_sha256: str,
    candidate_sha256: str | None = None,
    compile_error: str | None = None,
) -> dict:
    diagnostics = []
    objects = []
    if compile_error:
        diagnostics.append(
            {
                "id": "syntax-1",
                "kind": "syntax_error",
                "message": compile_error,
                "line": None,
                "offset": None,
            }
        )
        status = "syntax_error"
    else:
        for index, result in enumerate(results):
            if isinstance(result, CompileError):
                diagnostics.append(
                    {
                        "id": f"syntax-{index + 1}",
                        "kind": "syntax_error",
                        "message": str(result),
                        "line": None,
                        "offset": None,
                    }
                )
                continue
            bc = getattr(result, "bc_a", None)
            if bc is None:
                bc = getattr(result, "bc_b", None)
            name = getattr(bc, "name", "unknown") if bc is not None else "unknown"
            first_line = None
            if bc is not None:
                first_line = getattr(getattr(bc, "codeobj", None), "co_firstlineno", None)
            code_id = "co_" + hashlib.sha256(f"{index}:{name}".encode("utf-8")).hexdigest()[:12]
            entry = {
                "id": code_id,
                "name": name,
                "status": "perfect" if result.success else "semantic_error",
                "message": result.message,
                "line": result.failed_line_number,
                "offset": result.failed_offset,
                "first_line": first_line,
            }
            objects.append(entry)
            if not result.success:
                diagnostics.append(
                    {
                        "id": code_id,
                        "kind": "semantic_error",
                        "code_object_id": code_id,
                        "qualname": name,
                        "message": result.message,
                        "line": result.failed_line_number,
                        "offset": result.failed_offset,
                    }
                )
        if any(d["kind"] == "syntax_error" for d in diagnostics):
            status = "syntax_error"
        elif objects and all(o["status"] == "perfect" for o in objects):
            status = "perfect"
        elif objects:
            status = "semantic_error"
        else:
            status = "failed"

    perfect = sum(1 for item in objects if item["status"] == "perfect")
    syntax_errors = sum(1 for item in diagnostics if item["kind"] == "syntax_error")
    semantic_errors = sum(1 for item in objects if item["status"] != "perfect")
    total = len(objects)
    next_actions = [
        {
            "priority": index + 1,
            "code_object_id": item.get("code_object_id"),
            "reason": item.get("message", ""),
            "suggested_tool": "get_code_object",
        }
        for index, item in enumerate(diagnostics)
        if item.get("code_object_id")
    ]
    return {
        "schema_version": "1.0",
        "version": version,
        "status": status,
        "source_sha256": sha256_text(source),
        "candidate_sha256": candidate_sha256,
        "original_sha256": original_sha256,
        "summary": {
            "total": total,
            "perfect": perfect,
            "syntax_errors": syntax_errors,
            "semantic_errors": semantic_errors,
            "score": (perfect / total) if total else 0.0,
        },
        "code_objects": objects,
        "diagnostics": diagnostics,
        "next_actions": next_actions,
    }


def new_session(pyc_path: Path, version: str, options: dict) -> tuple[str, Path]:
    pyc_path = Path(pyc_path).resolve()
    if pyc_path.suffix.lower() != ".pyc":
        raise ValueError("input must be a .pyc file")
    if not pyc_path.is_file():
        raise FileNotFoundError(pyc_path)
    if pyc_path.stat().st_size > MAX_PYC_BYTES:
        raise ValueError(f"input exceeds {MAX_PYC_BYTES} bytes")
    SESSIONS.mkdir(parents=True, exist_ok=True)
    session_id = "ses_" + uuid.uuid4().hex[:16]
    directory = SESSIONS / session_id
    (directory / "input").mkdir(parents=True)
    (directory / "revisions" / "0000").mkdir(parents=True)
    (directory / "tmp").mkdir(parents=True)
    shutil.copy2(pyc_path, directory / "input" / "original.pyc")
    data = (directory / "input" / "original.pyc").read_bytes()
    meta = {
        "session_id": session_id,
        "created_at": now(),
        "input": {
            "path": str(pyc_path),
            "sha256": sha256_bytes(data),
            "size": len(data),
            "version": version,
        },
        "options": options,
        "current_revision": 0,
        "status": "running",
        "summary": {},
        "revisions": [],
    }
    _write_meta(session_id, meta)
    return session_id, directory / "revisions" / "0000" / "source.py"


def save_initial_revision(session_id: str, result, source: str) -> dict:
    source = normalize_source(source)
    directory = _session_dir(session_id)
    meta = _read_meta(session_id)
    report = _make_report(
        result.equivalence_results,
        version=str(result.version),
        source=source,
        original_sha256=meta["input"]["sha256"],
    )
    revision_dir = directory / "revisions" / "0000"
    atomic_write_text(revision_dir / "source.py", source)
    atomic_write_json(revision_dir / "report.json", report)
    revision_meta = {
        "revision": 0,
        "parent": None,
        "author": "decompiler",
        "description": "initial decompilation",
        "created_at": now(),
        "source_sha256": report["source_sha256"],
        "verification": {"status": report["status"], "summary": report["summary"]},
    }
    atomic_write_json(revision_dir / "meta.json", revision_meta)
    meta["current_revision"] = 0
    meta["status"] = report["status"]
    meta["summary"] = report["summary"]
    meta["revisions"] = [revision_meta]
    _write_meta(session_id, meta)
    return report


def import_source(pyc_path: Path, source: str, version: str, options: dict | None = None) -> tuple[str, dict]:
    """Create a session from an existing candidate source without re-decompiling."""
    source = normalize_source(source)
    session_id, source_path = new_session(Path(pyc_path), version, options or {"imported": True})
    report = _verify_source(session_id, source)
    meta = _read_meta(session_id)
    revision_dir = _session_dir(session_id) / "revisions" / "0000"
    atomic_write_text(source_path, source)
    atomic_write_json(revision_dir / "report.json", report)
    revision_meta = {
        "revision": 0,
        "parent": None,
        "author": "import",
        "description": "imported candidate source",
        "created_at": now(),
        "source_sha256": report["source_sha256"],
        "verification": {"status": report["status"], "summary": report["summary"]},
    }
    atomic_write_json(revision_dir / "meta.json", revision_meta)
    meta["current_revision"] = 0
    meta["status"] = report["status"]
    meta["summary"] = report["summary"]
    meta["revisions"] = [revision_meta]
    _write_meta(session_id, meta)
    return session_id, report


def get_session(session_id: str) -> dict:
    return _read_meta(session_id)


def mark_session_error(session_id: str, error: str) -> None:
    meta = _read_meta(session_id)
    meta["status"] = "failed"
    meta["error"] = error
    _write_meta(session_id, meta)


def get_source(session_id: str, revision: int | None = None) -> dict:
    revision, source = _source_for(session_id, revision)
    return {
        "session_id": session_id,
        "revision": revision,
        "source": source,
        "sha256": sha256_text(source),
        "lines": source.count("\n") + (0 if source.endswith("\n") else 1),
    }


def _report_view(
    report: dict,
    detail: str = "compact",
    max_diagnostics: int = 20,
    max_code_objects: int = 200,
) -> dict:
    if detail not in {"summary", "compact", "full"}:
        raise ValueError("detail must be summary, compact, or full")
    payload = dict(report)
    if detail == "full":
        return payload
    diagnostics = report.get("diagnostics", [])
    next_actions = report.get("next_actions", [])
    failing = [item for item in report.get("code_objects", []) if item["status"] != "perfect"]
    payload["diagnostics"] = diagnostics[: max(0, int(max_diagnostics))]
    payload["next_actions"] = next_actions[: max(0, int(max_diagnostics))]
    if detail == "compact":
        payload["code_objects"] = failing[: max(0, int(max_code_objects))]
    else:
        payload.pop("code_objects", None)
    payload["truncated"] = {
        "diagnostics": len(diagnostics) > len(payload["diagnostics"]),
        "next_actions": len(next_actions) > len(payload["next_actions"]),
        "code_objects": detail == "compact" and len(failing) > len(payload["code_objects"]),
    }
    return payload


def get_report(
    session_id: str,
    revision: int | None = None,
    detail: str = "full",
    max_diagnostics: int = 20,
    max_code_objects: int = 200,
) -> dict:
    revision, report = _report_for(session_id, revision)
    return {
        "session_id": session_id,
        "revision": revision,
        **_report_view(report, detail, max_diagnostics, max_code_objects),
    }


def list_code_objects(session_id: str, revision: int | None = None) -> list[dict]:
    _, report = _report_for(session_id, revision)
    return report.get("code_objects", [])


def get_code_object(session_id: str, code_object_id: str, revision: int | None = None) -> dict:
    revision, report = _report_for(session_id, revision)
    entry = next((item for item in report.get("code_objects", []) if item["id"] == code_object_id), None)
    if entry is None:
        raise KeyError(f"code object not found: {code_object_id}")
    session_dir = _session_dir(session_id)
    pyc = PYCFile(session_dir / "input" / "original.pyc")
    bytecode = next((bc for bc in pyc.iter_bytecodes() if bc.name == entry["name"]), None)
    instructions = []
    if bytecode is not None:
        for inst in bytecode.instructions:
            instructions.append(
                {
                    "offset": inst.offset,
                    "opname": inst.opname,
                    "arg": inst.arg,
                    "argval": repr(inst.argval),
                    "starts_line": getattr(inst, "starts_line", None),
                }
            )
    _, source = _source_for(session_id, revision)
    lines = source.splitlines()
    line = entry.get("line") or entry.get("first_line")
    source_slice = ""
    if line and 1 <= line <= len(lines):
        start = max(1, line - 8)
        end = min(len(lines), line + 20)
        source_slice = "\n".join(f"{i:5}: {lines[i - 1]}" for i in range(start, end + 1))
    return {
        "session_id": session_id,
        "revision": revision,
        "code_object": entry,
        "source_slice": source_slice,
        "bytecode": instructions,
    }


def _verify_source(session_id: str, source: str) -> dict:
    source = normalize_source(source)
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
    meta = _read_meta(session_id)
    directory = _session_dir(session_id)
    source_path = directory / "tmp" / "candidate.py"
    pyc_path = directory / "tmp" / "candidate.pyc"
    atomic_write_text(source_path, source)
    try:
        compile_with_toolchain(source_path, pyc_path, meta["input"]["version"])
    except CompileError as exc:
        return _make_report(
            [],
            version=meta["input"]["version"],
            source=source,
            original_sha256=meta["input"]["sha256"],
            compile_error=str(exc),
        )
    try:
        results = compare_pyc_strict(directory / "input" / "original.pyc", pyc_path)
    except Exception as exc:
        return _make_report(
            [],
            version=meta["input"]["version"],
            source=source,
            original_sha256=meta["input"]["sha256"],
            compile_error=f"verification failed: {exc!r}",
        )
    return _make_report(
        results,
        version=meta["input"]["version"],
        source=source,
        original_sha256=meta["input"]["sha256"],
        candidate_sha256=sha256_bytes(pyc_path.read_bytes()),
    )


def verify_source(session_id: str, source: str) -> dict:
    return {"session_id": session_id, "revision": "candidate", **_verify_source(session_id, source)}


def _patch_delta(session_id: str, parent_revision: int, report: dict) -> dict:
    _, parent_report = _report_for(session_id, parent_revision)
    parent = {item["id"]: item for item in parent_report.get("code_objects", [])}
    current = {item["id"]: item for item in report.get("code_objects", [])}
    fixed = [
        {"id": code_id, "name": current[code_id]["name"]}
        for code_id in sorted(current)
        if current[code_id]["status"] == "perfect" and parent.get(code_id, {}).get("status") != "perfect"
    ]
    regressed = [
        {"id": code_id, "name": parent[code_id]["name"]}
        for code_id in sorted(parent)
        if parent[code_id]["status"] == "perfect"
        and (code_id not in current or current[code_id]["status"] != "perfect")
    ]
    remaining = [
        {"id": item["id"], "name": item["name"], "status": item["status"], "message": item["message"]}
        for item in report.get("code_objects", [])
        if item["status"] != "perfect"
    ]
    parent_perfect = int(parent_report.get("summary", {}).get("perfect", 0))
    current_perfect = int(report.get("summary", {}).get("perfect", 0))
    return {
        "parent_revision": parent_revision,
        "fixed": fixed,
        "regressed": regressed,
        "remaining": remaining,
        "progress": {
            "parent_perfect": parent_perfect,
            "current_perfect": current_perfect,
            "delta": current_perfect - parent_perfect,
        },
    }


def apply_patch(
    session_id: str,
    base_revision: int,
    source: str,
    description: str = "",
    dry_run: bool = False,
    detail: str = "compact",
    max_code_objects: int = 200,
) -> dict:
    meta = _read_meta(session_id)
    current = _current_revision(meta)
    if int(base_revision) != current:
        return {
            "session_id": session_id,
            "error": "base_revision_mismatch",
            "expected": current,
            "received": int(base_revision),
        }
    source = normalize_source(source)
    report = _verify_source(session_id, source)
    delta = _patch_delta(session_id, current, report)
    view = _report_view(report, detail, max_code_objects=max_code_objects)
    if dry_run:
        return {"session_id": session_id, "revision": "candidate", **view, **delta}
    new_revision = current + 1
    directory = _session_dir(session_id) / "revisions" / f"{new_revision:04d}"
    directory.mkdir(parents=True)
    atomic_write_text(directory / "source.py", source)
    atomic_write_json(directory / "report.json", report)
    revision_meta = {
        "revision": new_revision,
        "parent": current,
        "author": "agent",
        "description": description,
        "created_at": now(),
        "source_sha256": report["source_sha256"],
        "verification": {"status": report["status"], "summary": report["summary"]},
    }
    atomic_write_json(directory / "meta.json", revision_meta)
    meta["current_revision"] = new_revision
    meta["status"] = report["status"]
    meta["summary"] = report["summary"]
    meta["revisions"].append(revision_meta)
    _write_meta(session_id, meta)
    return {"session_id": session_id, "revision": new_revision, **view, **delta}


def revert(session_id: str, target_revision: int) -> dict:
    meta = _read_meta(session_id)
    target_revision = int(target_revision)
    if not any(item["revision"] == target_revision for item in meta.get("revisions", [])):
        raise FileNotFoundError(f"revision {target_revision} not found")
    _, source = _source_for(session_id, target_revision)
    return apply_patch(
        session_id,
        _current_revision(meta),
        source,
        description=f"revert to revision {target_revision}",
    )


def export_source(session_id: str, revision: int | None = None) -> dict:
    revision, source = _source_for(session_id, revision)
    EXPORTS.mkdir(parents=True, exist_ok=True)
    path = EXPORTS / f"{session_id}_r{revision:04d}.py"
    atomic_write_text(path, source)
    return {
        "session_id": session_id,
        "revision": revision,
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256_text(source),
    }


def _decompiled_target(target: Path) -> Path:
    """Pick a free output path without ever replacing an existing source."""
    if not target.exists():
        return target
    index = 1
    while True:
        candidate = target.with_name(f"{target.stem}_decompiled_{index}{target.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def finalize_source(
    session_id: str,
    target_path: str | Path | None = None,
) -> dict:
    """Write a perfect revision beside its original .pyc.

    This is intentionally single-file: it never touches another session or
    another .pyc. A non-perfect session is rejected. Existing sources are never
    overwritten; the result gets a ``_decompiled_{i}`` suffix instead.

    Finalization re-runs exact verification instead of trusting the persisted
    report. Reports produced by an older comparator, or edited on disk, must not
    be able to bypass the current strict verifier.
    """
    meta = _read_meta(session_id)
    stored_report = get_report(session_id)
    if stored_report["status"] != "perfect":
        return {
            "session_id": session_id,
            "error": "not_perfect",
            "status": stored_report["status"],
            "summary": stored_report["summary"],
        }
    revision, source = _source_for(session_id)
    source_sha256 = sha256_text(source)
    stored_sha256 = str(stored_report.get("source_sha256", ""))
    if stored_sha256 != source_sha256:
        return {
            "session_id": session_id,
            "error": "source_hash_mismatch",
            "revision": revision,
            "expected_sha256": stored_sha256,
            "actual_sha256": source_sha256,
        }
    original_pyc = Path(meta["input"]["path"]).resolve()
    if not original_pyc.is_file():
        return {
            "session_id": session_id,
            "error": "original_pyc_missing",
            "original_pyc": str(original_pyc),
        }
    recorded_sha256 = str(meta.get("input", {}).get("sha256", ""))
    actual_sha256 = sha256_bytes(original_pyc.read_bytes())
    if recorded_sha256 and actual_sha256 != recorded_sha256:
        return {
            "session_id": session_id,
            "error": "original_pyc_changed",
            "original_pyc": str(original_pyc),
            "expected_sha256": recorded_sha256,
            "actual_sha256": actual_sha256,
        }
    requested = Path(target_path).expanduser() if target_path else original_pyc.with_suffix(".py")
    if not requested.is_absolute():
        requested = (original_pyc.parent / requested).resolve()
    else:
        requested = requested.resolve()
    if requested.suffix.lower() != ".py":
        return {"session_id": session_id, "error": "target_must_be_py", "target": str(requested)}
    if requested.parent != original_pyc.parent:
        return {
            "session_id": session_id,
            "error": "target_must_be_sibling",
            "target": str(requested),
            "original_pyc": str(original_pyc),
        }
    try:
        verified_report = _verify_source(session_id, source)
    except Exception as exc:
        return {
            "session_id": session_id,
            "error": "verification_failed",
            "revision": revision,
            "message": repr(exc),
        }
    if verified_report["status"] != "perfect":
        return {
            "session_id": session_id,
            "error": "not_perfect",
            "status": verified_report["status"],
            "summary": verified_report["summary"],
            "diagnostics": verified_report["diagnostics"][:20],
            "revision": revision,
            "reverified": True,
        }
    verified_sha256 = str(verified_report.get("source_sha256", ""))
    if verified_sha256 != source_sha256:
        return {
            "session_id": session_id,
            "error": "source_hash_mismatch",
            "revision": revision,
            "expected_sha256": verified_sha256,
            "actual_sha256": source_sha256,
        }
    target = _decompiled_target(requested)
    atomic_write_text(target, source)
    digest = source_sha256
    meta["finalized"] = {
        "path": str(target),
        "sha256": digest,
        "revision": revision,
        "created_at": now(),
    }
    _write_meta(session_id, meta)
    return {
        "session_id": session_id,
        "revision": revision,
        "status": "perfect",
        "requested_path": str(requested),
        "path": str(target),
        "renamed": target != requested,
        "sha256": digest,
        "reverified": True,
    }
