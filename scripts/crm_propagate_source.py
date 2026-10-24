from __future__ import annotations

import sys
from pathlib import Path

from pylingual_portable import sessions


def main() -> int:
    source_session = sys.argv[1]
    target_pyc = Path(sys.argv[2]).resolve()
    version = sys.argv[3]
    source = sessions.get_source(source_session)["source"]
    output = target_pyc.with_suffix(".py")
    output.write_text(source, encoding="utf-8")
    session_id, report = sessions.import_source(target_pyc, source, version, {"imported": "propagated"})
    print(output)
    print(session_id, report["status"], report["summary"])
    return 0 if report["status"] == "perfect" else 1


if __name__ == "__main__":
    raise SystemExit(main())
