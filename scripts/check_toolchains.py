from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLCHAINS = ROOT / "toolchains"
TMP = ROOT / "workspace" / "tmp" / "toolchain-check"
TMP.mkdir(parents=True, exist_ok=True)
SOURCE = TMP / "sample.py"
SOURCE.write_text("x = 1\nif x:\n    x += 1\n", encoding="utf-8")

failures = []
for python in sorted(TOOLCHAINS.glob("cpython-*-win-x64/python.exe")):
    version_dir = python.parent.name
    version = version_dir.removeprefix("cpython-").split("-")[0]
    output = TMP / f"sample-{version}.pyc"
    code = (
        "import py_compile, sys\n"
        f"py_compile.compile({str(SOURCE)!r}, cfile={str(output)!r}, doraise=True, optimize=0)\n"
        f"print(sys.version)\n"
    )
    result = subprocess.run(
        [str(python), "-I", "-S", "-c", code],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if result.returncode == 0 and output.exists():
        print(f"{version_dir}: OK ({result.stdout.strip().splitlines()[0]})")
    else:
        failures.append(version_dir)
        print(f"{version_dir}: FAIL")
        print(result.stderr.strip())
        print(result.stdout.strip())

if failures:
    raise SystemExit(1)
