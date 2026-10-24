from __future__ import annotations

import ast
import copy
from pathlib import Path

from pylingual.editable_bytecode import PYCFile
from pylingual_portable.toolchain import compile_with_toolchain


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "workspace" / "sessions" / "ses_02277b8be62a4f30" / "revisions" / "0003" / "source.py"
TMP = ROOT / "workspace" / "tmp" / "phish_probe"
TARGET = "pdf_feature_extraction"


def first_ops(path: Path):
    pyc = TMP / (path.stem + ".pyc")
    compile_with_toolchain(path, pyc, "3.6")
    target = next((bc for bc in PYCFile(pyc).iter_bytecodes() if bc.name == f"<module>.{TARGET}"), None)
    return [(inst.opname, str(inst.argval)) for inst in target.instructions[:10]] if target else []


def emit(module: ast.Module, name: str) -> Path:
    path = TMP / f"{name}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ast.unparse(module) + "\n", encoding="utf-8")
    return path


def main() -> int:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    func = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == TARGET)
    original = copy.deepcopy(func)
    assign = [node for node in func.body if isinstance(node, ast.Assign)][:3]
    ret = next(node for node in func.body if isinstance(node, ast.Return))
    variants = {}

    f = copy.deepcopy(func)
    f.body = assign + [ret]
    variants["assign_only"] = f

    f = copy.deepcopy(func)
    f.body = assign + [ast.Pass(), ret]
    variants["assign_pass_return"] = f

    f = copy.deepcopy(func)
    try_node = next(node for node in func.body if isinstance(node, ast.Try))
    t = copy.deepcopy(try_node)
    t.body = [ast.Pass()]
    f.body = assign + [t, ret]
    variants["assign_try_pass"] = f

    for name, variant in variants.items():
        module = ast.Module(body=[variant], type_ignores=[])
        path = emit(module, name)
        print(name, first_ops(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
