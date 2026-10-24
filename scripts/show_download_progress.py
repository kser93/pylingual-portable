from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROGRESS = ROOT / "downloads" / "progress"
STATUS = ROOT / "models" / "download-status"
VERSIONS = ["3.6", "3.7", "3.8", "3.9", "3.10", "3.11", "3.12", "3.13", "3.14", "3.15"]


def human_bytes(value: float) -> str:
    value = float(value or 0)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


def load(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def render() -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{stamp}] PyLingual model downloads", flush=True)
    print("version  status       current model/file                       progress                 speed          updated", flush=True)
    print("-" * 118, flush=True)
    for version in VERSIONS:
        data = load(PROGRESS / f"{version}.json")
        status = load(STATUS / f"{version}.json")
        progress_status = data.get("status") if data else None

        # A retry can be running while the previous status file still says error.
        if progress_status not in ("running", "error"):
            if status and status.get("status") == "done":
                print(f"{version:7}  done         {'-':46} {'-':24} {'-':14} {status.get('finished_at', '')}", flush=True)
                continue
            if status and status.get("status") == "error":
                print(f"{version:7}  error        {status.get('error', '')[:90]}", flush=True)
                continue
        if not data:
            print(f"{version:7}  waiting      {'-':46} {'-':24} {'-':14} -", flush=True)
            continue
        if progress_status == "error":
            print(f"{version:7}  error        {data.get('error', '')[:90]}", flush=True)
            continue
        current = data.get("current")
        if current:
            percent = current.get("percent", 0)
            progress_text = f"{percent:6.2f}% {human_bytes(current.get('bytes', 0))}/{human_bytes(current.get('total', 0))}"
            speed_text = f"{human_bytes(current.get('speed_bps', 0))}/s"
            label = f"{current.get('role', '?')}/{current.get('file', '?')}"
            eta = current.get("eta_seconds", 0)
            if eta:
                progress_text += f" ETA {int(eta)}s"
        else:
            label = "-"
            progress_text = "-"
            speed_text = "-"
        print(
            f"{version:7}  {data.get('status', '?'):11}  {label:46} {progress_text:24} {speed_text:14} {data.get('updated_at', '')}",
            flush=True,
        )
    print(flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Show live progress for PyLingual model downloads.")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--duration", type=float, default=0.0, help="0 = until Ctrl+C")
    args = parser.parse_args()

    PROGRESS.mkdir(parents=True, exist_ok=True)
    STATUS.mkdir(parents=True, exist_ok=True)
    if not args.watch:
        render()
        return 0

    started = time.monotonic()
    try:
        while True:
            render()
            if args.duration and time.monotonic() - started >= args.duration:
                return 0
            time.sleep(max(args.interval, 0.5))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
