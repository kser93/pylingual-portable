from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import HfApi


ROOT = Path(__file__).resolve().parent.parent
LINKS = ROOT / "models" / "model-links.json"
OUT = ROOT / "models" / "update-check.json"
ROLES = ("segmenter", "segmenter_tokenizer", "statement", "statement_tokenizer")


def main() -> int:
    api = HfApi()
    links = json.loads(LINKS.read_text(encoding="utf-8"))
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updates = []
    up_to_date = []
    errors = []

    print("version  role                   status      installed                          remote                             last modified")
    print("-" * 132)
    for version, roles in links.items():
        for role in ROLES:
            data = roles[role]
            repo = data["repo"]
            installed_sha = data["sha"]
            try:
                info = api.model_info(repo, files_metadata=False)
                remote_sha = info.sha
                last_modified = str(info.lastModified or "")
                if remote_sha == installed_sha:
                    status = "up-to-date"
                    up_to_date.append({"version": version, "role": role, "repo": repo, "sha": installed_sha})
                else:
                    status = "UPDATE"
                    updates.append(
                        {
                            "version": version,
                            "role": role,
                            "repo": repo,
                            "installed_sha": installed_sha,
                            "remote_sha": remote_sha,
                            "last_modified": last_modified,
                        }
                    )
                print(
                    f"{version:7}  {role:22} {status:11} {installed_sha:34} {remote_sha:34} {last_modified}"
                )
            except Exception as exc:
                status = "ERROR"
                errors.append({"version": version, "role": role, "repo": repo, "error": repr(exc)})
                print(f"{version:7}  {role:22} {status:11} {installed_sha:34} {'-':34} {exc!r}")

    result = {
        "checked_at": checked_at,
        "updates": updates,
        "up_to_date": up_to_date,
        "errors": errors,
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print(f"checked_at: {checked_at}")
    print(f"updates: {len(updates)}  up-to-date: {len(up_to_date)}  errors: {len(errors)}")
    print(f"written: {OUT}")
    return 2 if updates else (1 if errors else 0)


if __name__ == "__main__":
    raise SystemExit(main())
