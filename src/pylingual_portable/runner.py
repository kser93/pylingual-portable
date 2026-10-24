from __future__ import annotations

from pathlib import Path

import pylingual.decompiler as decompiler_module
from pylingual.decompiler import DecompilerResult, decompile
from pylingual.editable_bytecode import PYCFile

from .models import load_models
from .toolchain import compile_with_toolchain


def install_local_components() -> None:
    """Replace upstream network/uv/pyenv dependencies with local components."""
    decompiler_module.load_models = load_models
    decompiler_module.compile_version = compile_with_toolchain


def detect_version(pyc: Path) -> str:
    return str(PYCFile(pyc).version)


def decompile_file(
    pyc: Path,
    output: Path | None = None,
    version: str | None = None,
    top_k: int = 10,
    timeout: int | None = 600,
) -> DecompilerResult:
    install_local_components()
    pyc = Path(pyc).resolve()
    if not pyc.exists():
        raise FileNotFoundError(pyc)
    if version is None:
        version = detect_version(pyc)
    if output is not None:
        output = Path(output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
    return decompile(
        pyc=pyc,
        save_to=output,
        version=version,
        top_k=top_k,
        timeout=timeout,
    )
