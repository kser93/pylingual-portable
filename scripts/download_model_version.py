from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent.parent
LINKS = ROOT / "models" / "model-links.json"
CACHE = ROOT / "models" / "hf-cache" / "hub"
PROGRESS = ROOT / "downloads" / "progress"
STATUS = ROOT / "models" / "download-status"
ROLES = ("segmenter", "segmenter_tokenizer", "statement", "statement_tokenizer")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def human_bytes(value: float) -> str:
    value = float(value)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    last_error = None
    for attempt in range(6):
        try:
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(path)
            return
        except PermissionError as exc:
            # Windows antivirus/indexer can briefly lock the destination.
            last_error = exc
            time.sleep(0.2 * (attempt + 1))
    if last_error is not None:
        raise last_error


def load_progress(version: str) -> dict:
    path = PROGRESS / f"{version}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {
        "version": version,
        "status": "starting",
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "current": None,
        "roles": {role: {"status": "pending", "files": {}} for role in ROLES},
    }


def save_progress(data: dict) -> None:
    data["updated_at"] = utc_now()
    atomic_json(PROGRESS / f"{data['version']}.json", data)


def auth_headers() -> dict[str, str]:
    token = os.environ.get("HF_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def head_size(url: str) -> int:
    try:
        response = requests.head(url, allow_redirects=True, timeout=60, headers=auth_headers())
        response.raise_for_status()
        return int(response.headers.get("Content-Length", 0) or 0)
    except Exception:
        return 0


def download_file(
    url: str,
    dest: Path,
    version: str,
    role: str,
    filename: str,
    progress: dict,
    force: bool,
) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")

    if dest.exists() and not force:
        size = dest.stat().st_size
        print(f"[{version}/{role}/{filename}] already exists ({human_bytes(size)}); skip", flush=True)
        return size
    if force:
        for path in (dest, part):
            if path.exists():
                path.unlink()

    total = head_size(url)
    offset = part.stat().st_size if part.exists() else 0
    headers = {**auth_headers()}
    if offset:
        headers["Range"] = f"bytes={offset}-"

    print(
        f"[{version}/{role}/{filename}] start url={url} known_size={human_bytes(total) if total else 'unknown'}",
        flush=True,
    )
    started = time.monotonic()
    last_report = 0.0
    last_bytes = offset
    speed = 0.0
    downloaded = offset

    with requests.get(url, stream=True, headers=headers, timeout=120, allow_redirects=True) as response:
        if response.status_code == 416:
            part.replace(dest)
            return part.stat().st_size if part.exists() else dest.stat().st_size
        if offset and response.status_code == 200:
            offset = 0
            downloaded = 0
            mode = "wb"
        else:
            mode = "ab" if offset else "wb"
        response.raise_for_status()
        content_length = int(response.headers.get("Content-Length", 0) or 0)
        if content_length:
            total = content_length + offset

        with part.open(mode) as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if now - last_report >= 2.0 or (total and downloaded >= total):
                    elapsed = max(now - started, 0.001)
                    speed = (downloaded - offset) / elapsed
                    percent = (downloaded / total * 100.0) if total else 0.0
                    eta = ((total - downloaded) / speed) if total and speed > 0 else 0.0
                    print(
                        f"[{version}/{role}/{filename}] "
                        f"{percent:6.2f}% {human_bytes(downloaded)}/{human_bytes(total) if total else '?'} "
                        f"{human_bytes(speed)}/s ETA {int(eta)}s",
                        flush=True,
                    )
                    progress["current"] = {
                        "role": role,
                        "file": filename,
                        "bytes": downloaded,
                        "total": total,
                        "percent": round(percent, 2),
                        "speed_bps": round(speed, 1),
                        "eta_seconds": int(eta),
                    }
                    role_state = progress["roles"][role]
                    role_state["status"] = "downloading"
                    role_state["files"][filename] = {
                        "bytes": downloaded,
                        "total": total,
                        "percent": round(percent, 2),
                        "status": "downloading",
                    }
                    save_progress(progress)
                    last_report = now
                    last_bytes = downloaded

    if total and part.stat().st_size != total:
        raise IOError(f"size mismatch for {dest}: got {part.stat().st_size}, expected {total}")

    part.replace(dest)
    final_size = dest.stat().st_size
    role_state = progress["roles"][role]
    role_state["files"][filename] = {
        "bytes": final_size,
        "total": total or final_size,
        "percent": 100.0,
        "status": "done",
    }
    if all(item.get("status") == "done" for item in role_state["files"].values()):
        role_state["status"] = "done"
    save_progress(progress)
    print(f"[{version}/{role}/{filename}] done ({human_bytes(final_size)})", flush=True)
    return final_size


def main() -> int:
    parser = argparse.ArgumentParser(description="Download one PyLingual model pack with detailed progress.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--force", action="store_true", help="Download again even if files exist")
    parser.add_argument("--roles", default=",".join(ROLES), help="Comma-separated roles")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    version = args.version
    links_data = json.loads(LINKS.read_text(encoding="utf-8"))
    if version not in links_data:
        raise SystemExit(f"Version {version} not found in {LINKS}")
    selected_roles = [role.strip() for role in args.roles.split(",") if role.strip()]
    version_links = links_data[version]

    PROGRESS.mkdir(parents=True, exist_ok=True)
    STATUS.mkdir(parents=True, exist_ok=True)
    progress = load_progress(version)
    progress["status"] = "running"
    progress.pop("error", None)
    progress["started_at"] = progress.get("started_at") or utc_now()
    save_progress(progress)
    atomic_json(
        STATUS / f"{version}.json",
        {"version": version, "status": "running", "started_at": progress["started_at"]},
    )

    print(f"=== MODEL {version}: starting ===", flush=True)
    total_bytes = 0
    try:
        for role in selected_roles:
            role_links = version_links[role]
            repo = role_links["repo"]
            sha = role_links["sha"]
            repo_dir = CACHE / ("models--" + repo.replace("/", "--")) / "snapshots" / sha
            print(f"=== [{version}] {role}: {repo}@{sha} ===", flush=True)
            for filename, url in role_links["files"].items():
                if args.dry_run:
                    print(f"[dry-run] {version}/{role}/{filename} -> {url}", flush=True)
                    continue
                last_error = None
                for attempt in range(1, 4):
                    try:
                        total_bytes += download_file(
                            url=url,
                            dest=repo_dir / filename,
                            version=version,
                            role=role,
                            filename=filename,
                            progress=progress,
                            force=args.force and attempt == 1,
                        )
                        last_error = None
                        break
                    except Exception as exc:
                        last_error = exc
                        print(
                            f"[{version}/{role}/{filename}] attempt {attempt}/3 failed: {exc!r}",
                            flush=True,
                        )
                        if attempt < 3:
                            time.sleep(3 * attempt)
                if last_error is not None:
                    raise last_error
            refs = CACHE / ("models--" + repo.replace("/", "--")) / "refs"
            refs.mkdir(parents=True, exist_ok=True)
            (refs / "main").write_text(sha, encoding="utf-8")
            progress["roles"][role]["status"] = "done"

        progress["status"] = "done"
        progress["current"] = None
        progress["finished_at"] = utc_now()
        progress["total_bytes"] = total_bytes
        save_progress(progress)
        atomic_json(
            STATUS / f"{version}.json",
            {
                "version": version,
                "status": "done",
                "finished_at": utc_now(),
                "total_bytes": total_bytes,
                "roles": progress["roles"],
            },
        )
        print(f"=== MODEL {version}: DONE ({human_bytes(total_bytes)}) ===", flush=True)
        return 0
    except Exception as exc:
        progress["status"] = "error"
        progress["error"] = repr(exc)
        save_progress(progress)
        atomic_json(
            STATUS / f"{version}.json",
            {"version": version, "status": "error", "finished_at": utc_now(), "error": repr(exc)},
        )
        print(f"=== MODEL {version}: ERROR {exc!r} ===", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
