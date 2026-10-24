from __future__ import annotations

from pathlib import Path

print("stage: start", flush=True)

import torch
import transformers
from safetensors.torch import load_file
from transformers import AutoConfig, PreTrainedTokenizerFast, RobertaForTokenClassification

root = Path(__file__).resolve().parent.parent
hub = root / "models" / "hf-cache" / "hub"
seg_path = next((hub / "models--syssec-utd--py312-pylingual-v1-segmenter" / "snapshots").glob("*"))
seg_tok_path = next((hub / "models--syssec-utd--py312-pylingual-v1-tokenizer" / "snapshots").glob("*"))

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
config = AutoConfig.from_pretrained(seg_path, local_files_only=True)
model = RobertaForTokenClassification(config)
model.load_state_dict(load_file(str(seg_path / "model.safetensors"), device="cpu"), strict=True)
model.to(device).eval()
tokenizer = PreTrainedTokenizerFast(
    tokenizer_file=str(seg_tok_path / "tokenizer.json"),
    unk_token="[UNK]",
    pad_token="[PAD]",
    cls_token="[CLS]",
    sep_token="[SEP]",
    mask_token="[MASK]",
)

print("stage: pipeline", flush=True)
pipe = transformers.pipeline(
    "token-classification",
    model=model,
    tokenizer=tokenizer,
    aggregation_strategy="none",
    device=device,
)
print("stage: pipeline built", flush=True)

texts = ["LOAD_FAST <mask_0> <SEP> RETURN_VALUE", "LOAD_CONST <mask_1> <SEP> RETURN_VALUE"]
with torch.inference_mode():
    out = pipe(texts, batch_size=2)
print("output type:", type(out), "len:", len(out), flush=True)
for item in out:
    print("item len:", len(item), "first:", item[0] if item else None, flush=True)
print("stage: done", flush=True)
