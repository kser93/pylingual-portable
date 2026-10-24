from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "workspace" / "crm-inventory.json"
STATE = ROOT / "workspace" / "crm-state"


def norm(path: str) -> str:
    return path.replace("/", "\\")


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    targets = [item for item in inventory["records"] if not item.get("existing_source")]
    target_by_key = {norm(item["relative"]): item for item in targets}
    results = {}
    for path in (STATE / "results").glob("*.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        if norm(item["relative"]) in target_by_key:
            results[norm(item["relative"])] = item
    applied = set()
    for path in sorted((ROOT / "workspace").glob("crm-repairs-applied*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")):
            if item.get("applied"):
                applied.add(norm(item["relative"]))

    unresolved = []
    for key, target in target_by_key.items():
        if key in applied:
            continue
        result = results.get(key)
        if result and result.get("status") == "perfect":
            continue
        unresolved.append((key, target, result))

    no_py = [item for item in unresolved if not Path(item[1]["path"]).with_suffix(".py").is_file()]
    failed = [item for item in unresolved if item[2] and item[2].get("status") == "failed"]
    semantic = [item for item in unresolved if item[2] and item[2].get("status") == "semantic_error"]
    not_processed = [item for item in unresolved if item[2] is None]
    print(f"unresolved={len(unresolved)} no_py={len(no_py)} failed={len(failed)} semantic={len(semantic)} not_processed={len(not_processed)}")
    print("\nNo .py / failed / not processed:")
    for key, target, result in no_py:
        status = result.get("status") if result else "not_processed"
        print(f"  {status:20} {key}")
    print("\nSemantic failures by top directory:")
    for name, count in Counter(key.split("\\")[2] if len(key.split("\\")) > 2 else key for key, _, _ in semantic).most_common():
        print(f"  {count:4} {name}")
    print("\nSemantic failures by basename:")
    for name, count in Counter(Path(key).name for key, _, _ in semantic).most_common(30):
        print(f"  {count:4} {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
