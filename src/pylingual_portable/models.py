from __future__ import annotations

import gc
import os
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

from pylingual.models import CacheTranslator
from pylingual.utils.version import PythonVersion

from .paths import CONFIG, HF_HUB


_MODEL_CACHE: dict[tuple[str, str], tuple[object, CacheTranslator]] = {}


def _snapshot(repo_id: str) -> Path:
    folder = HF_HUB / ("models--" + repo_id.replace("/", "--"))
    snapshots = sorted((folder / "snapshots").glob("*"), key=lambda path: path.stat().st_mtime)
    if not snapshots:
        raise FileNotFoundError(
            f"Local model snapshot for {repo_id!r} was not found under {folder}. "
            "Run scripts/fetch_models_312.py or extend it for the required Python version."
        )
    return snapshots[-1]


def _load_model(path: Path, auto_class):
    config = AutoConfig.from_pretrained(path, local_files_only=True)
    model = auto_class.from_config(config)
    state = load_file(str(path / "model.safetensors"), device="cpu")
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
    """Load a local model pack without calling transformers.from_pretrained.

    transformers 5.19.0 currently crashes with an access violation in
    ``from_pretrained`` on the portable Python 3.15 + torch 2.14.1 stack.
    Building the model from its config and loading safetensors explicitly
    produces the same weights and works on both CPU and CUDA.
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

    seg_path = _snapshot(seg_config["REPO"])
    seg_tok_path = _snapshot(seg_config["TOKENIZER"])
    stmt_path = _snapshot(stmt_config["REPO"])
    stmt_tok_path = _snapshot(stmt_config["TOKENIZER"])

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
