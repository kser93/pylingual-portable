from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / "vendor" / "pylingual"
CONFIG = VENDOR / "pylingual" / "decompiler_config.yaml"
MODELS = ROOT / "models"
MODEL_LINKS = MODELS / "model-links.json"
HF_HUB = Path(os.environ.get("HF_HUB_CACHE", MODELS / "hf-cache" / "hub"))
TOOLCHAINS = ROOT / "toolchains"
WORKSPACE = ROOT / "workspace"
