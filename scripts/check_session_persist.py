from __future__ import annotations

import sys

from pylingual_portable.sessions import get_report, get_session, list_code_objects


def main() -> int:
    session_id = sys.argv[1]
    meta = get_session(session_id)
    report = get_report(session_id)
    objects = list_code_objects(session_id)
    print("session:", meta["session_id"], "status:", meta["status"], "revision:", meta["current_revision"])
    print("report:", report["status"], report["summary"])
    print("code_objects:", [(item["name"], item["status"]) for item in objects])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
