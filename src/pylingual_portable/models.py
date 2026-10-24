from __future__ import annotations

import gc
import json
import os
from functools import lru_cache
from pathlib import Path

import torch
import transformers
import yaml
from safetensors.torch import load_file
from transformers import (
    AutoConfig,
    AutoModelForSeq2SeqLM,
    AutoModelForTokenClassification,
    PreTrainedTokenizerFast,
    RobertaTokenizer,
)

from .paths import CONFIG, HF_HUB, MODEL_LINKS
from .upstream import CacheTranslator, PythonVersion


_MODEL_CACHE: dict[tuple[str, str], tuple[object, CacheTranslator]] = {}


@lru_cache(maxsize=1)
def _model_links() -> dict[str, dict[str, dict[str, str]]]:
    return json.loads(MODEL_LINKS.read_text(encoding="utf-8"))


def _linked_snapshot(version: PythonVersion, role: str, expected_repo: str) -> Path:
    """Resolve a model snapshot from the pinned repo/revision manifest.

    ``models/model-links.json`` records the Hugging Face repo and commit SHA for
    every role and Python version.  Using it here keeps runs reproducible even if
    a newer snapshot has been downloaded into the same cache.
    """
    version = PythonVersion(version)
    try:
        entry = _model_links()[version.as_str()][role]
    except KeyError as exc:
        raise FileNotFoundError(
            f"No pinned model entry for Python {version} role {role!r} in {MODEL_LINKS}. "
            "Run scripts/build_model_links.py and scripts/fetch_models.py."
        ) from exc
    repo = entry["repo"]
    revision = entry["sha"]
    if repo != expected_repo:
        raise RuntimeError(
            f"Model pin mismatch for Python {version} role {role!r}: "
            f"config expects {expected_repo!r}, {MODEL_LINKS.name} pins {repo!r}"
        )
    path = HF_HUB / ("models--" + repo.replace("/", "--")) / "snapshots" / revision
    if not path.is_dir():
        raise FileNotFoundError(
            f"Pinned model snapshot for {repo}@{revision} was not found at {path}. "
            f"Run scripts/fetch_models.py --versions {version} --revision {revision}."
        )
    return path


def _load_model(path: Path, auto_class):
    weights = path / "model.safetensors"
    if not weights.is_file():
        raise FileNotFoundError(f"model.safetensors not found in pinned snapshot: {path}")
    config = AutoConfig.from_pretrained(path, local_files_only=True)
    model = auto_class.from_config(config)
    state = load_file(str(weights), device="cpu")
    result = model.load_state_dict(state, strict=False)
    if result.unexpected_keys:
        raise RuntimeError(f"Unexpected weights in {path}: {result.unexpected_keys[:5]}")
    model.eval()
    return model


def _resolve_device(device: torch.device | str | None) -> torch.device:
    if device is not None:
        return torch.device(device)
    requested = os.environ.get("PYLINGUAL_DEVICE", "auto")
    if requested == "auto":
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    return torch.device(requested)


def load_models(
    config_file: Path = CONFIG,
    version: PythonVersion = PythonVersion((3, 9)),
    redis_cache_server_ip: str | None = None,
    redis_port: int = 6379,
    token: bool = False,
    device: torch.device | str | None = None,
) -> tuple[transformers.Pipeline, CacheTranslator]:
    """Load a pinned local model pack without calling transformers.from_pretrained.

    transformers 5.19.0 currently crashes with an access violation in
    ``from_pretrained`` on the portable Python 3.15 + torch 2.14.1 stack.
    Building the model from its config and loading safetensors explicitly
    produces the same weights and works on both CPU and CUDA.

    Exactly one snapshot per repo is used: the commit SHA recorded in
    ``models/model-links.json``.  Newer snapshots in the cache are ignored.
    """
    del redis_cache_server_ip, redis_port, token

    version = PythonVersion(version)
    selected_device = _resolve_device(device)
    key = (version.as_str(), str(selected_device))
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]

    config = yaml.safe_load(Path(config_file).read_text(encoding="utf-8"))[f"v{version}"]
    seg_config = config["SEGMENTATION_MODEL"]
    stmt_config = config["STATEMENT_MODEL"]

    seg_path = _linked_snapshot(version, "segmenter", seg_config["REPO"])
    seg_tok_path = _linked_snapshot(version, "segmenter_tokenizer", seg_config["TOKENIZER"])
    stmt_path = _linked_snapshot(version, "statement", stmt_config["REPO"])
    stmt_tok_path = _linked_snapshot(version, "statement_tokenizer", stmt_config["TOKENIZER"])

    segmenter_model = _load_model(seg_path, AutoModelForTokenClassification)
    segmenter_tokenizer = PreTrainedTokenizerFast(
        tokenizer_file=str(seg_tok_path / "tokenizer.json"),
        unk_token="[UNK]",
        pad_token="[PAD]",
        cls_token="[CLS]",
        sep_token="[SEP]",
        mask_token="[MASK]",
    )
    segmenter = transformers.pipeline(
        "token-classification",
        model=segmenter_model,
        tokenizer=segmenter_tokenizer,
        aggregation_strategy="none",
        device=selected_device,
    )

    statement_model = _load_model(stmt_path, AutoModelForSeq2SeqLM)
    statement_tokenizer = RobertaTokenizer.from_pretrained(
        stmt_tok_path,
        local_files_only=True,
        clean_up_tokenization_spaces=False,
    )
    translator = CacheTranslator(
        statement_model,
        statement_tokenizer,
        python_version=version.as_str(),
        device=selected_device,
    )

    if _MODEL_CACHE:
        _MODEL_CACHE.clear()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    _MODEL_CACHE[key] = (segmenter, translator)
    return segmenter, translator
