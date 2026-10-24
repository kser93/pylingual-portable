from __future__ import annotations

from pathlib import Path

print("stage: start", flush=True)
from safetensors import safe_open
import safetensors

print("safetensors:", safetensors.__version__, flush=True)

root = Path(__file__).resolve().parent.parent
path = next((root / "models" / "hf-cache" / "hub" / "models--syssec-utd--py312-pylingual-v1-segmenter" / "snapshots").glob("*")) / "model.safetensors"
print("path:", path, "size:", path.stat().st_size, flush=True)

print("stage: safe_open", flush=True)
with safe_open(path, framework="numpy") as handle:
    keys = list(handle.keys())
    print("keys:", len(keys), keys[:5], flush=True)
    tensor = handle.get_tensor(keys[0])
    print("tensor:", tensor.shape, tensor.dtype, float(tensor.reshape(-1)[0]), flush=True)

print("stage: torch load", flush=True)
import torch
from safetensors.torch import load_file

state = load_file(str(path), device="cpu")
print("torch state keys:", len(state), flush=True)
print("stage: done", flush=True)
