from __future__ import annotations

from pathlib import Path

from .upstream import DecompilerResult, PYCFile, decompile, install_local_components


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
