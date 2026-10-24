from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def kill_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    else:
        process.kill()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pyc")
    parser.add_argument("--version", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output", default=None)
    parser.add_argument("--result", default=None)
    args = parser.parse_args()
    pyc = Path(args.pyc).resolve()
    output = Path(args.output).resolve() if args.output else pyc.with_suffix(".py")
    command = [
        sys.executable,
        str(ROOT / "scripts" / "crm_decompile_one.py"),
        str(pyc),
        "--version",
        args.version,
        "--output",
        str(output),
        "--top-k",
        str(args.top_k),
    ]
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=args.timeout)
        code = process.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_tree(process)
        stdout, stderr = process.communicate()
        code = process.returncode
    result = {
        "pyc": str(pyc),
        "output": str(output),
        "version": args.version,
        "top_k": args.top_k,
        "timeout_seconds": args.timeout,
        "timed_out": timed_out,
        "exit_code": code,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout": stdout[-4000:],
        "stderr": stderr[-4000:],
    }
    if args.result:
        result_path = Path(args.result).resolve()
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("pyc", "timed_out", "exit_code", "duration_seconds")}, indent=2))
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
