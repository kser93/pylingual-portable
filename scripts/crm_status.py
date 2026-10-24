from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "workspace" / "crm-inventory.json"
STATE = ROOT / "workspace" / "crm-state"


def key(relative: str) -> str:
    return relative.replace("/", "\\")


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    targets = [item for item in inventory["records"] if not item.get("existing_source")]
    target_by_key = {key(item["relative"]): item for item in targets}
    target_keys = set(target_by_key)
    results = {}
    for path in (STATE / "results").glob("*.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        if key(item["relative"]) in target_keys:
            results[key(item["relative"])] = item

    applied = {}
    for path in sorted((ROOT / "workspace").glob("crm-repairs-applied*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")):
            if item.get("applied"):
                applied[key(item["relative"])] = item
    session_applied = ROOT / "workspace" / "crm-session-applied.json"
    if session_applied.is_file():
        for item in json.loads(session_applied.read_text(encoding="utf-8")):
            applied[key(item["relative"])] = item

    skip = set()
    skip_path = STATE / "skip.txt"
    if skip_path.is_file():
        skip = {
            key(line.strip())
            for line in skip_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

    batch_counts = Counter(item.get("status", "unknown") for item in results.values())
    perfect = {rel for rel, item in results.items() if item.get("status") == "perfect"}
    covered = perfect | set(applied)
    unresolved = target_keys - covered
    no_py = []
    for item in targets:
        pyc = Path(item["path"])
        if not pyc.with_suffix(".py").is_file():
            no_py.append(item["relative"])
    unresolved_details = []
    for rel in sorted(unresolved):
        result = results.get(rel, {})
        target = target_by_key[rel]
        unresolved_details.append(
            {
                "relative": rel,
                "batch_status": result.get("status", "not_processed"),
                "batch_summary": result.get("summary"),
                "known_skip": rel in skip,
                "has_py": Path(target["path"]).with_suffix(".py").is_file(),
            }
        )

    output = {
        "targets_total": len(targets),
        "batch_results": len(results),
        "batch_statuses": dict(batch_counts),
        "batch_perfect": len(perfect),
        "repaired_applied": len(applied),
        "covered_perfect": len(covered),
        "unresolved": len(unresolved),
        "targets_without_py": len(no_py),
        "known_skipped": len(skip),
        "unresolved_details": unresolved_details,
    }
    print(json.dumps({k: output[k] for k in output if k != "unresolved_details"}, indent=2))
    print("\nUnresolved:")
    for item in unresolved_details:
        print(
            f"  {item['batch_status']:24} "
            f"skip={item['known_skip']} "
            f"py={item['has_py']} "
            f"{item['relative']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
