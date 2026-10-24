from __future__ import annotations

import sys

from pylingual_portable.sessions import get_report


def main() -> int:
    session_id = sys.argv[1]
    for detail in ("summary", "compact", "full"):
        report = get_report(session_id, detail=detail)
        print(
            detail,
            "status=", report["status"],
            "summary=", report["summary"],
            "has_code_objects=", "code_objects" in report,
            "code_objects=", len(report.get("code_objects", [])),
            "truncated=", report.get("truncated"),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
