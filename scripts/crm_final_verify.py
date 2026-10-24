from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pylingual.equivalence_check import compare_pyc

from pylingual_portable.toolchain import compile_with_toolchain


ROOT = Path(__file__).resolve().parent.parent


def verify_one(item: dict, work_dir: Path) -> dict:
    pyc = Path(item["path"])
    source = pyc.with_suffix(".py")
    if not source.is_file():
        return {**item, "verification": "missing_source", "output": str(source)}
    candidate = work_dir / f"{item['sha256'][:16]}-{pyc.stem}.pyc"
    try:
        compile_with_toolchain(source, candidate, item["version"])
        results = list(compare_pyc(pyc, candidate))
        perfect = sum(1 for result in results if getattr(result, "success", False))
        total = len(results)
        failures = []
        for result in results:
            if getattr(result, "success", False):
                continue
            failures.append(
                {
                    "message": getattr(result, "message", str(result)),
                    "line": getattr(result, "failed_line_number", None),
                    "offset": getattr(result, "failed_offset", None),
                }
            )
            if len(failures) >= 20:
                break
        return {
            **item,
            "output": str(source),
            "verification": "perfect" if total and perfect == total else "mismatch",
            "summary": {"total": total, "perfect": perfect, "score": (perfect / total) if total else 0.0},
            "failures": failures,
        }
    except Exception as exc:
        return {**item, "output": str(source), "verification": "failed", "error": repr(exc)}
    finally:
        candidate.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify CRM recovered .py files against original .pyc")
    parser.add_argument("--inventory", default=str(ROOT / "workspace" / "crm-inventory.json"))
    parser.add_argument("--output", default=str(ROOT / "workspace" / "crm-final-verification.json"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--include-existing", action="store_true")
    args = parser.parse_args()

    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    records = [
        item
        for item in inventory.get("records", [])
        if args.include_existing or not item.get("existing_source")
    ]
    work_dir = ROOT / "workspace" / "crm-verify"
    work_dir.mkdir(parents=True, exist_ok=True)
    print(f"verify targets: {len(records)}")
    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(verify_one, item, work_dir): item for item in records}
        for index, future in enumerate(as_completed(futures), 1):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({**futures[future], "verification": "failed", "error": repr(exc)})
            if index % 25 == 0:
                print(f"verified {index}/{len(records)}", flush=True)
    results.sort(key=lambda item: item["relative"])
    counts = {}
    for item in results:
        counts[item["verification"]] = counts.get(item["verification"], 0) + 1
    summary = {
        "inventory": str(Path(args.inventory).resolve()),
        "targets": len(results),
        "counts": counts,
        "perfect": counts.get("perfect", 0),
        "mismatch_or_failed": len(results) - counts.get("perfect", 0),
        "results": results,
    }
    output = Path(args.output).resolve()
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("targets", "counts", "perfect", "mismatch_or_failed")}, indent=2))
    print(f"output: {output}")
    return 0 if summary["mismatch_or_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
