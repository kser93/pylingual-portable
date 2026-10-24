from __future__ import annotations

import sys

from pylingual_portable import sessions


OLD = "and 'response' in enrichers['url_rep'] and len(enrichers['url_rep']['response']) > 0"
NEW = "and 'response' in enrichers['url_rep'] and isinstance(enrichers['url_rep']['response'], list) and len(enrichers['url_rep']['response']) > 0"


def main() -> int:
    session_id = sys.argv[1]
    meta = sessions.get_session(session_id)
    source = sessions.get_source(session_id)["source"]
    if OLD not in source:
        print("pattern not found")
        return 2
    patched = source.replace(OLD, NEW, 1)
    result = sessions.apply_patch(
        session_id,
        int(meta["current_revision"]),
        patched,
        description="restore isinstance(response, list) in get_vt url_rep chain",
    )
    print(result["status"], result["summary"], result.get("fixed"), result.get("remaining"))
    return 0 if result["status"] == "perfect" else 1


if __name__ == "__main__":
    raise SystemExit(main())
