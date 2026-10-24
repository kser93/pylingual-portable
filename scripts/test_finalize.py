from __future__ import annotations

import shutil
from pathlib import Path

from pylingual_portable import sessions


ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / "workspace" / "tmp" / "finalize-test"


def main() -> int:
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    pyc = TMP / "simple.pyc"
    shutil.copy2(ROOT / "workspace" / "samples" / "simple.pyc", pyc)
    source = (ROOT / "workspace" / "samples" / "topk10-test.py").read_text(encoding="utf-8")
    session_id, report = sessions.import_source(pyc, source, "3.12")
    print("import:", session_id, report["status"], report["summary"])
    first = sessions.finalize_source(session_id)
    print("first:", first)
    second = sessions.finalize_source(session_id)
    print("second:", second)
    third = sessions.finalize_source(session_id)
    print("third:", third)
    paths = [Path(item["path"]) for item in (first, second, third)]
    expected = [TMP / "simple.py", TMP / "simple_decompiled_1.py", TMP / "simple_decompiled_2.py"]
    print("paths exist:", [path.is_file() for path in paths])
    return 0 if paths == expected and all(path.is_file() for path in paths) else 1


if __name__ == "__main__":
    raise SystemExit(main())
