from __future__ import annotations

from pathlib import Path

print("stage: start", flush=True)

import torch
from safetensors.torch import load_file
from transformers import AutoConfig, PreTrainedTokenizerFast, RobertaForTokenClassification, RobertaTokenizer, T5ForConditionalGeneration

root = Path(__file__).resolve().parent.parent
hub = root / "models" / "hf-cache" / "hub"

seg_path = next((hub / "models--syssec-utd--py312-pylingual-v1-segmenter" / "snapshots").glob("*"))
seg_tok_path = next((hub / "models--syssec-utd--py312-pylingual-v1-tokenizer" / "snapshots").glob("*"))
stmt_path = next((hub / "models--syssec-utd--py312-pylingual-v1-statement" / "snapshots").glob("*"))
stmt_tok_path = next((hub / "models--syssec-utd--py312-pylingual-v1-tok" / "snapshots").glob("*"))

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print("device:", device, flush=True)

print("stage: segmenter config/build/load", flush=True)
seg_config = AutoConfig.from_pretrained(seg_path, local_files_only=True)
segmenter = RobertaForTokenClassification(seg_config)
segmenter.load_state_dict(load_file(str(seg_path / "model.safetensors"), device="cpu"), strict=True)
segmenter.to(device).eval()
print("segmenter parameters:", sum(p.numel() for p in segmenter.parameters()), flush=True)

print("stage: statement config/build/load", flush=True)
stmt_config = AutoConfig.from_pretrained(stmt_path, local_files_only=True)
statement = T5ForConditionalGeneration(stmt_config)
result = statement.load_state_dict(load_file(str(stmt_path / "model.safetensors"), device="cpu"), strict=False)
print("statement missing keys:", len(result.missing_keys), flush=True)
statement.to(device).eval()
print("statement parameters:", sum(p.numel() for p in statement.parameters()), flush=True)

print("stage: tokenizers", flush=True)
seg_tokenizer = PreTrainedTokenizerFast(
    tokenizer_file=str(seg_tok_path / "tokenizer.json"),
    unk_token="[UNK]",
    pad_token="[PAD]",
    cls_token="[CLS]",
    sep_token="[SEP]",
    mask_token="[MASK]",
)
stmt_tokenizer = RobertaTokenizer.from_pretrained(stmt_tok_path, local_files_only=True)
print("segmenter tokenizer:", len(seg_tokenizer), flush=True)
print("statement tokenizer:", len(stmt_tokenizer), flush=True)

print("stage: segmenter forward", flush=True)
inputs = seg_tokenizer(["LOAD_FAST <mask_0> <SEP> RETURN_VALUE"], return_tensors="pt", padding=True)
inputs = {key: value.to(device) for key, value in inputs.items()}
with torch.inference_mode():
    logits = segmenter(**inputs).logits
print("segmenter logits:", tuple(logits.shape), "device:", logits.device, flush=True)

print("stage: statement generate", flush=True)
encoded = stmt_tokenizer(["LOAD_FAST <mask_0> <SEP> RETURN_VALUE"], return_tensors="pt", padding=True)
encoded = {key: value.to(device) for key, value in encoded.items()}
with torch.inference_mode():
    output = statement.generate(**encoded, max_new_tokens=8)
print("statement output shape:", tuple(output.shape), "device:", output.device, flush=True)
print("statement decoded:", stmt_tokenizer.decode(output[0], skip_special_tokens=False), flush=True)

print("stage: done", flush=True)
