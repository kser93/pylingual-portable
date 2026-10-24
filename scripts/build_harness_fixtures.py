from __future__ import annotations

import argparse
from pathlib import Path

from pylingual_portable.toolchain import compile_with_toolchain


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "harness" / "fixtures"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile OpenCode harness fixtures with a local target toolchain")
    parser.add_argument("--version", default="3.12", help="target Python version, e.g. 3.12")
    parser.add_argument("--force", action="store_true", help="recompile existing .pyc files")
    args = parser.parse_args()

    sources = sorted((FIXTURES / "src").glob("*.py"))
    if not sources:
        raise SystemExit(f"no fixture sources under {FIXTURES / 'src'}")
    output = FIXTURES / "pyc" / args.version
    output.mkdir(parents=True, exist_ok=True)
    compiled = 0
    skipped = 0
    for source in sources:
        target = output / f"{source.stem}.pyc"
        if target.exists() and not args.force:
            print(f"skip {source.name} -> {target.relative_to(ROOT)}")
            skipped += 1
            continue
        compile_with_toolchain(source, target, args.version)
        print(f"built {source.name} -> {target.relative_to(ROOT)} ({target.stat().st_size} bytes)")
        compiled += 1
    print(f"compiled={compiled} skipped={skipped} version={args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
