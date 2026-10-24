"""Single integration point for the embedded PyLingual upstream components.

All imports of :mod:`pylingual` used by the portable wrapper go through this
module.  The upstream source itself is never edited; only two functions are
replaced at runtime (``load_models`` and ``compile_version``) so that the
decompiler can run fully offline with local model snapshots and local Python
toolchains.

Exports are resolved lazily (PEP 562), so importing :mod:`pylingual_portable`
does not pull in torch/transformers unless a caller actually asks for a heavy
symbol.  This keeps patch verification and MCP metadata endpoints fast.
"""

from __future__ import annotations

import functools
import importlib
import inspect
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - type-checking only
    from pylingual.decompiler import DecompilerResult, decompile
    from pylingual.editable_bytecode import PYCFile
    from pylingual.equivalence_check import compare_pyc
    from pylingual.models import CacheTranslator
    from pylingual.utils.generate_bytecode import CompileError
    from pylingual.utils.version import PythonVersion


_EXPORTS: dict[str, tuple[str, str | None]] = {
    "CacheTranslator": ("pylingual.models", "CacheTranslator"),
    "CompileError": ("pylingual.utils.generate_bytecode", "CompileError"),
    "DecompilerResult": ("pylingual.decompiler", "DecompilerResult"),
    "PYCFile": ("pylingual.editable_bytecode", "PYCFile"),
    "PythonVersion": ("pylingual.utils.version", "PythonVersion"),
    "compare_pyc": ("pylingual.equivalence_check", "compare_pyc"),
    "decompile": ("pylingual.decompiler", "decompile"),
    "decompiler_module": ("pylingual.decompiler", None),
}


def __getattr__(name: str) -> Any:
    """Resolve an upstream symbol on first use."""
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    module = importlib.import_module(module_name)
    value = module if attribute is None else getattr(module, attribute)
    globals()[name] = value
    return value


def _require_parameters(obj: Any, required: tuple[str, ...], label: str) -> list[str]:
    try:
        parameters = inspect.signature(obj).parameters
    except (TypeError, ValueError) as exc:
        return [f"{label}: cannot inspect signature: {exc!r}"]
    missing = [name for name in required if name not in parameters]
    if missing:
        return [f"{label}: missing parameter(s): {', '.join(missing)}"]
    return []


@functools.lru_cache(maxsize=1)
def assert_contract() -> dict[str, Any]:
    """Fail fast if upstream changes the API surface the wrapper relies on.

    The check is intentionally narrow: it verifies the names and parameters
    that the portable wrapper actually uses, not the whole upstream package.
    It is safe to call repeatedly and is cached after the first success.
    """
    from pylingual import decompiler as decompiler_module
    from pylingual.editable_bytecode import PYCFile
    from pylingual.equivalence_check import compare_pyc
    from pylingual.models import CacheTranslator
    from pylingual.utils.generate_bytecode import CompileError
    from pylingual.utils.version import PythonVersion

    errors: list[str] = []
    errors += _require_parameters(
        decompiler_module.decompile,
        ("pyc", "save_to", "config_file", "version", "top_k", "timeout"),
        "pylingual.decompiler.decompile",
    )
    errors += _require_parameters(
        compare_pyc,
        ("pyc_a", "pyc_b"),
        "pylingual.equivalence_check.compare_pyc",
    )
    errors += _require_parameters(PYCFile.__init__, ("source",), "PYCFile.__init__")
    errors += _require_parameters(
        CacheTranslator.__init__,
        ("model", "tokenizer", "python_version", "device"),
        "CacheTranslator.__init__",
    )

    result_fields = getattr(decompiler_module.DecompilerResult, "__dataclass_fields__", {})
    for field in ("decompiled_source", "equivalence_results", "original_pyc", "version"):
        if field not in result_fields:
            errors.append(f"DecompilerResult: missing field: {field}")

    for attribute in ("load_models", "compile_version"):
        if not hasattr(decompiler_module, attribute):
            errors.append(f"pylingual.decompiler: missing monkeypatch target: {attribute}")

    if not hasattr(PYCFile, "save"):
        errors.append("PYCFile: missing method: save")
    for method in ("as_str", "as_tuple"):
        if not hasattr(PythonVersion, method):
            errors.append(f"PythonVersion: missing method: {method}")
    if not (isinstance(CompileError, type) and issubclass(CompileError, Exception)):
        errors.append("CompileError is not an exception class")

    if errors:
        raise RuntimeError("PyLingual upstream contract mismatch:\n- " + "\n- ".join(errors))
    return {
        "ok": True,
        "checked": [
            "pylingual.decompiler.decompile",
            "pylingual.decompiler.load_models",
            "pylingual.decompiler.compile_version",
            "pylingual.equivalence_check.compare_pyc",
            "pylingual.editable_bytecode.PYCFile",
            "pylingual.models.CacheTranslator",
            "pylingual.utils.version.PythonVersion",
            "pylingual.utils.generate_bytecode.CompileError",
        ],
    }


def install_local_components() -> None:
    """Replace upstream network/uv/pyenv dependencies with local components.

    This is the only runtime modification to upstream.  The source tree in
    ``vendor/pylingual`` stays byte-identical to the pinned release.
    """
    import pylingual.decompiler as decompiler_module

    from .models import load_models
    from .toolchain import compile_with_toolchain

    assert_contract()
    decompiler_module.load_models = load_models
    decompiler_module.compile_version = compile_with_toolchain
