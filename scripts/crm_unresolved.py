from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "workspace" / "crm-inventory.json"
STATE = ROOT / "workspace" / "crm-state"
OUTPUT = ROOT / "workspace" / "crm-unresolved.json"


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
    session_applied = ROOT / "workspace" / "crm-session-applied.json"
    if session_applied.is_file():
        for item in json.loads(session_applied.read_text(encoding="utf-8")):
            applied.add(norm(item["relative"]))

    unresolved = []
    for key, target in sorted(target_by_key.items()):
        if key in applied:
            continue
        result = results.get(key)
        if result and result.get("status") == "perfect":
            continue
        source = Path(target["path"]).with_suffix(".py")
        unresolved.append(
            {
                "relative": key,
                "path": target["path"],
                "version": target["version"],
                "status": result.get("status", "not_processed") if result else "not_processed",
                "has_py": source.is_file(),
                "source_path": str(source),
                "summary": result.get("summary") if result else None,
                "failures": result.get("failures", []) if result else [],
                "error": result.get("error") if result else None,
            }
        )
    OUTPUT.write_text(json.dumps(unresolved, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"unresolved={len(unresolved)} output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
