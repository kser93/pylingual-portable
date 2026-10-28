from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVENTORY = ROOT / "workspace" / "batch-inventory.json"
DEFAULT_VERIFY = ROOT / "workspace" / "batch-final-verification.json"
DEFAULT_MARKER = ROOT / "workspace" / "BATCH_DECOMPILE_COMPLETE.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the batch outputs and write a completion marker")
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--verify", default=str(DEFAULT_VERIFY))
    parser.add_argument("--marker", default=str(DEFAULT_MARKER))
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    verify_path = Path(args.verify).resolve()
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "batch_final_verify.py"),
            "--inventory",
            str(Path(args.inventory).resolve()),
            "--output",
            str(verify_path),
            "--workers",
            str(args.workers),
        ],
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if not verify_path.is_file():
        print("verification report was not created", file=sys.stderr)
        return 2
    report = json.loads(verify_path.read_text(encoding="utf-8"))
    targets = int(report.get("targets", 0))
    perfect = int(report.get("perfect", 0))
    failed = int(report.get("mismatch_or_failed", targets - perfect))
    unresolved = [
        {
            "relative": item.get("relative"),
            "verification": item.get("verification"),
            "error": item.get("error"),
            "summary": item.get("summary"),
        }
        for item in report.get("results", [])
        if item.get("verification") != "perfect"
    ]
    status = "complete" if targets > 0 and perfect == targets and failed == 0 else "incomplete"
    marker = {
        "status": status,
        "scope": ".pyc modules without an adjacent source file",
        "targets": targets,
        "perfect": perfect,
        "mismatch_or_failed": failed,
        "unresolved": unresolved,
        "verification": str(verify_path),
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    Path(args.marker).resolve().write_text(json.dumps(marker, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: marker[key] for key in ("status", "targets", "perfect", "mismatch_or_failed")}, indent=2))
    print(f"marker: {Path(args.marker).resolve()}")
    return 0 if status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
