from __future__ import annotations

from pathlib import Path

print("stage: start", flush=True)

import torch
from safetensors.torch import load_file
from transformers import AutoConfig, RobertaForTokenClassification, T5ForConditionalGeneration

root = Path(__file__).resolve().parent.parent
hub = root / "models" / "hf-cache" / "hub"

seg_path = next((hub / "models--syssec-utd--py312-pylingual-v1-segmenter" / "snapshots").glob("*"))
stmt_path = next((hub / "models--syssec-utd--py312-pylingual-v1-statement" / "snapshots").glob("*"))

print("stage: seg config", flush=True)
seg_config = AutoConfig.from_pretrained(seg_path, local_files_only=True)
print("stage: seg build", flush=True)
seg = RobertaForTokenClassification(seg_config)
print("stage: seg state load", flush=True)
seg_state = load_file(str(seg_path / "model.safetensors"), device="cpu")
result = seg.load_state_dict(seg_state, strict=False)
print("seg missing:", len(result.missing_keys), "unexpected:", len(result.unexpected_keys), flush=True)
print("stage: seg eval", flush=True)
seg.eval()
with torch.no_grad():
    out = seg(input_ids=torch.tensor([[1, 2, 3, 4]]), attention_mask=torch.ones(1, 4, dtype=torch.long))
print("seg logits:", out.logits.shape, flush=True)

print("stage: stmt config", flush=True)
stmt_config = AutoConfig.from_pretrained(stmt_path, local_files_only=True)
print("stage: stmt build", flush=True)
stmt = T5ForConditionalGeneration(stmt_config)
print("stage: stmt state load", flush=True)
stmt_state = load_file(str(stmt_path / "model.safetensors"), device="cpu")
result = stmt.load_state_dict(stmt_state, strict=False)
print("stmt missing:", len(result.missing_keys), "unexpected:", len(result.unexpected_keys), flush=True)
print("stage: done", flush=True)
