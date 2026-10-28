from __future__ import annotations

import argparse
import json
from pathlib import Path

from pylingual_portable.runner import decompile_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pyc")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    import os

    os.environ["PYLINGUAL_DEVICE"] = args.device
    pyc = Path(args.pyc).resolve()
    output = Path(args.output).resolve() if args.output else pyc.with_suffix(".py")
    result = decompile_file(pyc, output=output, version=args.version, top_k=args.top_k, timeout=args.timeout)
    equivalence = list(getattr(result, "equivalence_results", []) or [])
    perfect = sum(1 for item in equivalence if getattr(item, "success", False))
    total = len(equivalence)
    print(
        json.dumps(
            {
                "pyc": str(pyc),
                "output": str(output),
                "status": "perfect" if total and perfect == total else "semantic_error",
                "perfect": perfect,
                "total": total,
                "score": (perfect / total) if total else 0.0,
            },
            ensure_ascii=False,
        )
    )
    return 0 if total and perfect == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
