from __future__ import annotations

import sys

from pylingual_portable import sessions


def main() -> int:
    session_id = sys.argv[1]
    base = int(sessions.get_session(session_id)["current_revision"])
    source = sessions.get_source(session_id)["source"]
    bad = source.replace("return a + b", "return a - b", 1)
    if bad == source:
        print("fixture does not contain the expected line")
        return 2
    result = sessions.apply_patch(session_id, base, bad, description="delta test: bad arithmetic")
    print(
        "bad:",
        result["status"],
        result["summary"],
        "fixed=", [item["name"] for item in result["fixed"]],
        "regressed=", [item["name"] for item in result["regressed"]],
        "remaining=", [item["name"] for item in result["remaining"]],
        "progress=", result["progress"],
    )
    result = sessions.apply_patch(session_id, result["revision"], source, description="delta test: restore")
    print(
        "restore:",
        result["status"],
        result["summary"],
        "fixed=", [item["name"] for item in result["fixed"]],
        "regressed=", [item["name"] for item in result["regressed"]],
        "remaining=", [item["name"] for item in result["remaining"]],
        "progress=", result["progress"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
