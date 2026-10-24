from __future__ import annotations

import os
import sys

print("stage: start", flush=True)
print("python:", sys.version, flush=True)

import torch

print("stage: torch", torch.__version__, "cuda", torch.cuda.is_available(), flush=True)

import transformers
from transformers import AutoModelForTokenClassification, T5ForConditionalGeneration

print("stage: transformers", transformers.__version__, flush=True)

from pathlib import Path

root = Path(__file__).resolve().parent.parent
hub = root / "models" / "hf-cache" / "hub"
seg_path = next((hub / "models--syssec-utd--py312-pylingual-v1-segmenter" / "snapshots").glob("*"))
stmt_path = next((hub / "models--syssec-utd--py312-pylingual-v1-statement" / "snapshots").glob("*"))
print("stage: seg snapshot", seg_path, flush=True)
print("stage: stmt snapshot", stmt_path, flush=True)

print("stage: loading segmenter", flush=True)
segmenter = AutoModelForTokenClassification.from_pretrained(seg_path, local_files_only=True)
print("stage: segmenter loaded", type(segmenter).__name__, flush=True)

print("stage: loading statement", flush=True)
statement = T5ForConditionalGeneration.from_pretrained(stmt_path, local_files_only=True)
print("stage: statement loaded", type(statement).__name__, flush=True)

if os.environ.get("TEST_CUDA", "0") == "1" and torch.cuda.is_available():
    print("stage: moving to cuda", flush=True)
    segmenter.to("cuda")
    statement.to("cuda")
    print("stage: moved to cuda", flush=True)

print("stage: done", flush=True)
