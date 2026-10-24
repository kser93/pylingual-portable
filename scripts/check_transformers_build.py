from __future__ import annotations

from pathlib import Path

print("stage: start", flush=True)

import torch
import torch.nn as nn

print("stage: torch", torch.__version__, flush=True)
linear = nn.Linear(4, 4)
print("stage: linear", linear.weight.shape, flush=True)
print("stage: linear forward", linear(torch.zeros(2, 4)).shape, flush=True)

from transformers import AutoConfig, RobertaForTokenClassification, T5ForConditionalGeneration

print("stage: transformers imported", flush=True)

root = Path(__file__).resolve().parent.parent
hub = root / "models" / "hf-cache" / "hub"
seg_path = next((hub / "models--syssec-utd--py312-pylingual-v1-segmenter" / "snapshots").glob("*"))
stmt_path = next((hub / "models--syssec-utd--py312-pylingual-v1-statement" / "snapshots").glob("*"))

print("stage: load seg config", flush=True)
seg_config = AutoConfig.from_pretrained(seg_path, local_files_only=True)
print("seg config:", seg_config.model_type, seg_config.num_hidden_layers, flush=True)

print("stage: build seg from config", flush=True)
seg = RobertaForTokenClassification(seg_config)
print("stage: seg built", sum(p.numel() for p in seg.parameters()), flush=True)

print("stage: load stmt config", flush=True)
stmt_config = AutoConfig.from_pretrained(stmt_path, local_files_only=True)
print("stmt config:", stmt_config.model_type, stmt_config.num_layers, flush=True)

print("stage: build stmt from config", flush=True)
stmt = T5ForConditionalGeneration(stmt_config)
print("stage: stmt built", sum(p.numel() for p in stmt.parameters()), flush=True)

print("stage: done", flush=True)
