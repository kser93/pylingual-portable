from __future__ import annotations

import json
from pathlib import Path

import yaml
from huggingface_hub import HfApi


ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "vendor" / "pylingual" / "pylingual" / "decompiler_config.yaml"
OUT_MD = ROOT / "docs" / "model-download-links.md"
OUT_JSON = ROOT / "models" / "model-links.json"

REQUIRED = {
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
        "tokenizer.json",
        "merges.txt",
        "vocab.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
    ],
}


def main() -> int:
    api = HfApi()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    versions = [key[1:] for key in config if key.startswith("v3.")]
    result: dict[str, dict[str, dict]] = {}
    lines = [
        "# PyLingual model download links",
        "",
        "Ссылки привязаны к commit SHA, который был актуален на момент генерации файла.",
        "Для каждой версии нужны четыре репозитория: segmenter, segmenter tokenizer, statement, statement tokenizer.",
        "",
        "Быстрый способ скачать всё локально:",
        "",
        "```powershell",
        r".\scripts\python.cmd .\scripts\fetch_models.py --versions all",
        "```",
        "",
        "Скрипт использует `HF_HUB_DISABLE_XET=1` и раскладывает файлы в `models/hf-cache`.",
        "",
    ]

    for version in versions:
        version_config = config[f"v{version}"]
        repos = {
            "segmenter": version_config["SEGMENTATION_MODEL"]["REPO"],
            "segmenter_tokenizer": version_config["SEGMENTATION_MODEL"]["TOKENIZER"],
            "statement": version_config["STATEMENT_MODEL"]["REPO"],
            "statement_tokenizer": version_config["STATEMENT_MODEL"]["TOKENIZER"],
        }
        result[version] = {}
        lines.extend([f"## Python {version}", "", "| Компонент | Репозиторий | Commit | Файлы |", "|---|---|---|---|"])
        for role, repo_id in repos.items():
            info = api.model_info(repo_id, files_metadata=False)
            sha = info.sha
            available = {s.rfilename for s in info.siblings}
            files = [name for name in REQUIRED[role] if name in available]
            repo_url = f"https://huggingface.co/{repo_id}"
            tree_url = f"{repo_url}/tree/{sha}"
            file_links = [
                f"https://huggingface.co/{repo_id}/resolve/{sha}/{name}?download=true"
                for name in files
            ]
            result[version][role] = {
                "repo": repo_id,
                "sha": sha,
                "repo_url": repo_url,
                "tree_url": tree_url,
                "files": dict(zip(files, file_links)),
            }
            links = "<br>".join(f"[{name}]({url})" for name, url in zip(files, file_links))
            lines.append(f"| {role} | [{repo_id}]({repo_url}) | [`{sha}`]({tree_url}) | {links} |")
        lines.append("")

    lines.extend(
        [
            "## Примечания",
            "",
            "- `model.safetensors` — веса; `config.json` — архитектура; tokenizer-файлы — токенизатор.",
            "- Для statement-моделей tokenizer вынесен в отдельный репозиторий (`...-tok`).",
            "- Для segmenter токенизатор тоже вынесен отдельно (`...-tokenizer`).",
            "- Если ссылка `resolve/<sha>` устарела, замените `<sha>` на актуальный commit из [Hugging Face](https://huggingface.co/syssec-utd).",
            "- 3.6 и 3.12 уже скачаны локально; повторная загрузка перезапишет/проверит кэш.",
        ]
    )

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_JSON}")
    for version in versions:
        print(version, {role: data["sha"] for role, data in result[version].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
