from __future__ import annotations

import sys

from pylingual_portable import sessions


def main() -> int:
    target_session = sys.argv[1]
    source_session = sys.argv[2]
    source = sessions.get_source(source_session)["source"]
    current = int(sessions.get_session(target_session)["current_revision"])
    result = sessions.apply_patch(
        target_session,
        current,
        source,
        description=f"copy exact source from {source_session}",
    )
    print(target_session, result["status"], result.get("summary"))
    return 0 if result["status"] == "perfect" else 1


if __name__ == "__main__":
    raise SystemExit(main())
