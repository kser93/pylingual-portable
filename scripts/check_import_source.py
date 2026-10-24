from __future__ import annotations

import sys
from pathlib import Path

from pylingual_portable import sessions


def main() -> int:
    pyc = Path(sys.argv[1]).resolve()
    source = pyc.with_suffix(".py").read_text(encoding="utf-8")
    version = sys.argv[2] if len(sys.argv) > 2 else "3.9"
    session_id, report = sessions.import_source(pyc, source, version)
    print(session_id, report["status"], report["summary"])
    print("revision:", sessions.get_session(session_id)["current_revision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
