from __future__ import annotations

import argparse
import difflib
from pathlib import Path

from pylingual.editable_bytecode import PYCFile

from pylingual_portable import sessions
from pylingual_portable.strict_verification import compare_pyc_strict as compare_pyc
from pylingual_portable.toolchain import compile_with_toolchain


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session_id")
    parser.add_argument("--revision", type=int, default=None)
    parser.add_argument("--name", default=None)
    args = parser.parse_args()
    meta = sessions.get_session(args.session_id)
    revision, source = sessions._source_for(args.session_id, args.revision)
    original = sessions._session_dir(args.session_id) / "input" / "original.pyc"
    temp = sessions._session_dir(args.session_id) / "tmp" / "diff_candidate.py"
    candidate = sessions._session_dir(args.session_id) / "tmp" / "diff_candidate.pyc"
    temp.write_text(source, encoding="utf-8")
    compile_with_toolchain(temp, candidate, meta["input"]["version"])
    results = compare_pyc(original, candidate)
    for result in results:
        if result.success:
            continue
        if args.name and args.name not in result.names():
            continue
        print("=" * 100)
        print(result.names(), result.message, result.failed_line_number, result.failed_offset)
        a = [(inst.opname, str(inst.argval)) for inst in result.bc_a.instructions] if result.bc_a else []
        b = [(inst.opname, str(inst.argval)) for inst in result.bc_b.instructions] if result.bc_b else []
        for line in difflib.unified_diff(
            [f"{index:04d} {op} {arg}" for index, (op, arg) in enumerate(a)],
            [f"{index:04d} {op} {arg}" for index, (op, arg) in enumerate(b)],
            fromfile="original",
            tofile="candidate",
            n=8,
        ):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
