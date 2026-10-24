from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINKS = ROOT / "models" / "model-links.json"
STATUS = ROOT / "models" / "download-status"
CACHE = ROOT / "models" / "hf-cache" / "hub"
VERSIONS = ["3.6", "3.7", "3.8", "3.9", "3.10", "3.11", "3.12", "3.13", "3.14", "3.15"]


def human_bytes(value: float) -> str:
    value = float(value or 0)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


def main() -> int:
    links = json.loads(LINKS.read_text(encoding="utf-8"))
    installed: dict[str, dict[str, str]] = {}
    print("version  status      segmenter     statement     total         files")
    print("-" * 92)
    failures = 0
    for version in VERSIONS:
        status = {}
        status_path = STATUS / f"{version}.json"
        if status_path.exists():
            status = json.loads(status_path.read_text(encoding="utf-8"))
        sizes = {"segmenter": 0, "statement": 0}
        total_size = 0
        files_ok = 0
        files_total = 0
        for role in ("segmenter", "segmenter_tokenizer", "statement", "statement_tokenizer"):
            data = links[version][role]
            repo_dir = CACHE / ("models--" + data["repo"].replace("/", "--")) / "snapshots" / data["sha"]
            for filename in data["files"]:
                files_total += 1
                path = repo_dir / filename
                if path.exists() and path.stat().st_size > 0:
                    files_ok += 1
                    total_size += path.stat().st_size
                    if filename == "model.safetensors" and role in sizes:
                        sizes[role] = path.stat().st_size
        complete = status.get("status") == "done" and files_ok == files_total
        if complete:
            installed[version] = {
                role: (CACHE / ("models--" + links[version][role]["repo"].replace("/", "--")) / "snapshots" / links[version][role]["sha"]).relative_to(ROOT).as_posix()
                for role in ("segmenter", "segmenter_tokenizer", "statement", "statement_tokenizer")
            }
        else:
            failures += 1
        print(
            f"{version:7}  {status.get('status', 'missing'):10}  "
            f"{human_bytes(sizes['segmenter']):12}  {human_bytes(sizes['statement']):12}  "
            f"{human_bytes(total_size):12}  {files_ok}/{files_total}"
        )

    (ROOT / "models" / "installed.json").write_text(
        json.dumps({"installed": installed, "failures": {}}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\ncomplete versions: {len(installed)}/{len(VERSIONS)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
