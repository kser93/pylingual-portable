from __future__ import annotations

import os
import subprocess
from pathlib import Path

from pylingual.utils.generate_bytecode import CompileError
from pylingual.utils.version import PythonVersion

from .paths import ROOT, TOOLCHAINS, WORKSPACE


# Extend this mapping as new toolchain packs are installed.
TOOLCHAINS_BY_VERSION: dict[tuple[int, int], str] = {
    (3, 12): "cpython-3.12.15-win-x64",
}


def toolchain_python(version: PythonVersion | str | tuple[int, int]) -> Path:
    version = PythonVersion(version)
    directory = TOOLCHAINS_BY_VERSION.get(version.as_tuple())
    if directory is not None:
        python = TOOLCHAINS / directory / "python.exe"
        if python.exists():
            return python

    # Fall back to any installed pack for the requested major.minor.
    candidates = sorted(
        TOOLCHAINS.glob(f"cpython-{version.major}.{version.minor}*-win-x64/python.exe"),
        key=lambda path: path.as_posix(),
    )
    if not candidates:
        raise CompileError(
            f"No local CPython toolchain for {version}. "
            f"Install it under {TOOLCHAINS}."
        )
    return candidates[-1]


def compile_with_toolchain(py_file: str | Path, out_file: str | Path, version: PythonVersion | str | tuple[int, int]) -> None:
    version = PythonVersion(version)
    python = toolchain_python(version)
    py_file = Path(py_file).resolve()
    out_file = Path(out_file).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    code = (
        "import py_compile, sys\n"
        f"py_compile.compile({str(py_file)!r}, cfile={str(out_file)!r}, doraise=True, optimize=0)\n"
        "assert sys.version_info[:2] == " + repr(version.as_tuple()) + "\n"
    )
    env = {
        **os.environ,
        "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMP": str(WORKSPACE / "tmp"),
        "TEMP": str(WORKSPACE / "tmp"),
    }
    (WORKSPACE / "tmp").mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(python), "-I", "-S", "-c", code],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"CPython {version} compilation failed"
        raise CompileError(message)
