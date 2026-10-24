"""Verify that embedded upstream components match their pinned trees.

The manifest at ``vendor/components.json`` records the upstream repository,
commit, license, patch list and a content hash for each vendored component.
This script is intentionally offline: it hashes the local tree and compares it
with the recorded hash.  It never clones or downloads anything.

Usage:
    python scripts/check_vendor.py
    python scripts/check_vendor.py --update   # manual, after a reviewed sync
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "vendor" / "components.json"
ALGORITHM = "sha256-tree-v1"


def _is_excluded(relative: Path, spec: dict[str, Any]) -> bool:
    excluded_dirs = set(spec.get("exclude_dirs", []))
    if any(part in excluded_dirs for part in relative.parts):
        return True
    text = relative.as_posix()
    name = relative.name
    for pattern in spec.get("exclude_globs", []):
        if fnmatch.fnmatchcase(text, pattern) or fnmatch.fnmatchcase(name, pattern):
            return True
    return False


def _iter_files(root: Path, spec: dict[str, Any]) -> list[Path]:
    paths = [
        path
        for path in root.rglob("*")
        if path.is_file() and not _is_excluded(path.relative_to(root), spec)
    ]
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def tree_hash(root: Path, spec: dict[str, Any]) -> tuple[str, int]:
    """Return a deterministic hash of relative paths and normalized contents.

    CRLF is normalized to LF so the hash is stable across Git's autocrlf
    settings on Windows and Linux checkouts.
    """
    digest = hashlib.sha256()
    files = _iter_files(root, spec)
    for path in files:
        relative = path.relative_to(root).as_posix()
        content = path.read_bytes().replace(b"\r\n", b"\n")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest(), len(files)


def _check_component(
    name: str,
    spec: dict[str, Any],
    *,
    update: bool,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    root = ROOT / spec["path"]
    summary: dict[str, Any] = {
        "path": spec["path"],
        "version": spec.get("version"),
        "commit": spec.get("commit"),
        "license": spec.get("license"),
        "patches": len(spec.get("patches", [])),
    }
    if not root.is_dir():
        errors.append(f"{name}: component path does not exist: {spec['path']}")
        return summary, errors

    actual, count = tree_hash(root, spec)
    if update:
        spec["tree_sha256"] = actual
        spec["file_count"] = count
    expected = spec.get("tree_sha256")
    if not expected:
        errors.append(f"{name}: tree_sha256 is not pinned in {MANIFEST}")
    elif expected != actual:
        errors.append(
            f"{name}: local tree differs from the pinned snapshot "
            f"(expected {expected}, actual {actual})"
        )
    expected_count = spec.get("file_count")
    if expected_count is not None and expected_count != count:
        errors.append(f"{name}: expected {expected_count} files, found {count}")

    license_file = ROOT / spec.get("license_file", "")
    if not license_file.is_file():
        errors.append(f"{name}: license file is missing: {spec.get('license_file')}")

    for patch in spec.get("patches", []):
        if not (ROOT / patch).is_file():
            errors.append(f"{name}: patch file is missing: {patch}")

    commit = str(spec.get("commit", ""))
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        errors.append(f"{name}: commit must be a full 40-character lowercase SHA")

    summary.update({"tree_sha256": actual, "files": count})
    return summary, errors


def check_components(*, update: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    if not MANIFEST.is_file():
        return {
            "ok": False,
            "manifest": str(MANIFEST),
            "components": {},
            "errors": [f"manifest not found: {MANIFEST}"],
        }

    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "manifest": str(MANIFEST),
            "components": {},
            "errors": [f"invalid manifest JSON: {exc}"],
        }

    if manifest.get("algorithm") != ALGORITHM:
        errors.append(f"unsupported hash algorithm: {manifest.get('algorithm')!r}")
    raw_components = manifest.get("components", {})
    if not raw_components:
        errors.append("manifest has no components")

    summaries: dict[str, Any] = {}
    for name, spec in raw_components.items():
        summary, component_errors = _check_component(name, spec, update=update)
        summaries[name] = summary
        errors.extend(component_errors)

    if update:
        manifest["verified_at"] = datetime.now(timezone.utc).date().isoformat()
        MANIFEST.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return {
        "ok": not errors,
        "manifest": str(MANIFEST),
        "algorithm": ALGORITHM,
        "components": summaries,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify embedded upstream components")
    parser.add_argument(
        "--update",
        action="store_true",
        help="recompute and write tree hashes (manual, after a reviewed upstream sync)",
    )
    args = parser.parse_args()

    result = check_components(update=args.update)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
