from __future__ import annotations

import sys

from pylingual_portable import sessions


OLD = """                                if 'score' in cadet_json and 'ndarray' in cadet_json['score']:
                                        try:"""
NEW = """                                if 'score' in cadet_json:
                                    if 'ndarray' in cadet_json['score']:
                                        try:"""


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
        description="split score/ndarray condition into nested ifs",
    )
    print(result["status"], result["summary"], result.get("fixed"), result.get("remaining"))
    return 0 if result["status"] == "perfect" else 1


if __name__ == "__main__":
    raise SystemExit(main())
