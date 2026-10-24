from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from pylingual.editable_bytecode import PYCFile


PYCACHE_TAG = re.compile(r"\.cpython-\d+$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_candidates(pyc: Path) -> list[Path]:
    candidates = [pyc.with_suffix(".py")]
    if pyc.parent.name == "__pycache__":
        base = PYCACHE_TAG.sub("", pyc.stem)
        candidates.append(pyc.parent.parent / f"{base}.py")
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory .pyc files in a tree")
    parser.add_argument("root")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    records = []
    versions = Counter()
    errors = []
    for directory, _, files in os.walk(root):
        for name in files:
            if not name.lower().endswith(".pyc"):
                continue
            path = Path(directory) / name
            try:
                version = str(PYCFile(path).version)
            except Exception as exc:
                errors.append({"path": str(path), "error": repr(exc)})
                version = "unknown"
            candidates = source_candidates(path)
            existing = next((item for item in candidates if item.is_file()), None)
            records.append(
                {
                    "path": str(path),
                    "relative": path.relative_to(root).as_posix(),
                    "version": version,
                    "size": path.stat().st_size,
                    "sha256": sha256(path),
                    "in_pycache": path.parent.name == "__pycache__",
                    "source_candidates": [str(item) for item in candidates],
                    "existing_source": str(existing) if existing else None,
                }
            )
            versions[version] += 1
    duplicates = defaultdict(list)
    for record in records:
        duplicates[record["sha256"]].append(record["path"])
    duplicate_groups = [paths for paths in duplicates.values() if len(paths) > 1]
    report = {
        "root": str(root),
        "pyc_count": len(records),
        "pyc_bytes": sum(item["size"] for item in records),
        "versions": dict(sorted(versions.items())),
        "in_pycache": sum(1 for item in records if item["in_pycache"]),
        "with_existing_source": sum(1 for item in records if item["existing_source"]),
        "without_existing_source": sum(1 for item in records if not item["existing_source"]),
        "unique_hashes": len(duplicates),
        "duplicate_groups": len(duplicate_groups),
        "duplicate_files": sum(len(paths) - 1 for paths in duplicate_groups),
        "errors": errors,
        "records": records,
    }
    output = Path(args.output).resolve() if args.output else root / "pyc-inventory.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"root={root}")
    print(f"pyc={len(records)} bytes={report['pyc_bytes']}")
    print(f"versions={report['versions']}")
    print(f"in_pycache={report['in_pycache']} with_source={report['with_existing_source']} without_source={report['without_existing_source']}")
    print(f"unique_hashes={report['unique_hashes']} duplicate_groups={report['duplicate_groups']} duplicate_files={report['duplicate_files']}")
    print(f"errors={len(errors)} output={output}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
