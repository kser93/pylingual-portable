from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import yaml
from huggingface_hub import snapshot_download


ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "vendor" / "pylingual" / "pylingual" / "decompiler_config.yaml"
LINKS = ROOT / "models" / "model-links.json"
CACHE = Path(os.environ.get("HF_HUB_CACHE", ROOT / "models" / "hf-cache" / "hub"))

ALLOW_PATTERNS = {
    "segmenter": [
        "config.json",
        "model.safetensors",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
    ],
    "segmenter_tokenizer": ["tokenizer.json"],
    "statement": [
        "config.json",
        "generation_config.json",
        "model.safetensors",
        "merges.txt",
        "vocab.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
    ],
    "statement_tokenizer": [
        "merges.txt",
        "vocab.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
    ],
}


def versions_from_config() -> list[str]:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return [key[1:] for key in config if key.startswith("v3.")]


def main() -> int:
    parser = argparse.ArgumentParser(description="Download PyLingual model packs into the local HF cache.")
    parser.add_argument("--versions", default="all", help="'all' or comma-separated versions, e.g. 3.12,3.13")
    parser.add_argument(
        "--revision",
        default=None,
        help="HF revision to download; default: the pinned SHA from models/model-links.json",
    )
    parser.add_argument("--force", action="store_true", help="Re-download files even if they are already cached")
    args = parser.parse_args()

    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    links: dict[str, dict[str, dict[str, str]]] = {}
    if LINKS.exists():
        try:
            links = json.loads(LINKS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            links = {}
    versions = versions_from_config() if args.versions == "all" else [v.strip() for v in args.versions.split(",")]
    CACHE.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
    # hf-xet stalled on some older model repos in this environment; HTTP is slower but reliable.
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

    manifest_path = ROOT / "models" / "installed.json"
    existing = {"installed": {}, "failures": {}}
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    installed: dict[str, dict[str, str]] = existing.get("installed", {})
    failures: dict[str, str] = existing.get("failures", {})

    for version in versions:
        version_config = config[f"v{version}"]
        seg = version_config["SEGMENTATION_MODEL"]
        stmt = version_config["STATEMENT_MODEL"]
        repos = {
            "segmenter": seg["REPO"],
            "segmenter_tokenizer": seg["TOKENIZER"],
            "statement": stmt["REPO"],
            "statement_tokenizer": stmt["TOKENIZER"],
        }
        installed[version] = {}
        for role, repo_id in repos.items():
            revision = args.revision or links.get(version, {}).get(role, {}).get("sha", "main")
            print(f"[{version}] {role}: {repo_id}@{revision}", flush=True)
            try:
                path = snapshot_download(
                    repo_id=repo_id,
                    revision=revision,
                    cache_dir=str(CACHE),
                    allow_patterns=ALLOW_PATTERNS[role],
                    force_download=args.force,
                )
                try:
                    stored_path = Path(path).relative_to(ROOT).as_posix()
                except ValueError:
                    stored_path = path
                installed[version][role] = stored_path
                print(f"[{version}] {role} -> {path}", flush=True)
            except Exception as exc:
                failures[f"{version}:{role}"] = repr(exc)
                print(f"[{version}] {role} FAILED: {exc}", flush=True)
        manifest_path.write_text(
            json.dumps({"installed": installed, "failures": failures}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    print(json.dumps({"installed": sorted(installed), "failures": failures}, indent=2, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
