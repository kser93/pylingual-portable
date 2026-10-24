from __future__ import annotations

import json
from pathlib import Path

from safetensors import safe_open

ROOT = Path(__file__).resolve().parent.parent
LINKS = ROOT / "models" / "model-links.json"
CACHE = ROOT / "models" / "hf-cache" / "hub"


def main() -> int:
    links = json.loads(LINKS.read_text(encoding="utf-8"))
    failures = []
    print("version  segmenter tensors  statement tensors  sizes")
    print("-" * 72)
    for version, roles in links.items():
        counts = {}
        sizes = {}
        for role in ("segmenter", "statement"):
            data = roles[role]
            path = CACHE / ("models--" + data["repo"].replace("/", "--")) / "snapshots" / data["sha"] / "model.safetensors"
            try:
                with safe_open(path, framework="numpy") as handle:
                    counts[role] = len(list(handle.keys()))
                sizes[role] = path.stat().st_size
            except Exception as exc:
                failures.append((version, role, repr(exc)))
                counts[role] = -1
                sizes[role] = 0
        print(
            f"{version:7}  {counts['segmenter']:16}  {counts['statement']:16}  "
            f"{sizes['segmenter'] / (1024**2):.0f} MiB / {sizes['statement'] / (1024**2):.0f} MiB"
        )
    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(failure)
        return 1
    print("\nall safetensors headers are readable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
