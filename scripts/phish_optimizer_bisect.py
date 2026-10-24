from __future__ import annotations

import ast
import copy
from pathlib import Path

from pylingual.editable_bytecode import PYCFile
from pylingual_portable.toolchain import compile_with_toolchain


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "workspace" / "sessions" / "ses_02277b8be62a4f30" / "revisions" / "0003" / "source.py"
TMP = ROOT / "workspace" / "tmp" / "phish_bisect"
TARGET = "pdf_feature_extraction"


def main() -> int:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    func = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == TARGET)
    assign = [node for node in func.body if isinstance(node, ast.Assign)][:3]
    ret = next(node for node in func.body if isinstance(node, ast.Return))
    try_node = next(node for node in func.body if isinstance(node, ast.Try))
    TMP.mkdir(parents=True, exist_ok=True)
    for count in range(0, len(try_node.body) + 1):
        f = copy.deepcopy(func)
        t = copy.deepcopy(try_node)
        t.body = copy.deepcopy(try_node.body[:count]) or [ast.Pass()]
        f.body = assign + [t, ret]
        module = ast.Module(body=[f], type_ignores=[])
        path = TMP / f"variant_{count}.py"
        path.write_text(ast.unparse(module) + "\n", encoding="utf-8")
        pyc = TMP / f"variant_{count}.pyc"
        compile_with_toolchain(path, pyc, "3.6")
        target = next((bc for bc in PYCFile(pyc).iter_bytecodes() if bc.name == f"<module>.{TARGET}"), None)
        first = [(inst.opname, str(inst.argval)) for inst in target.instructions[:6]] if target else []
        folded = any(op == "LOAD_CONST" and "(0, 0, 0, 0)" in arg for op, arg in first)
        print(count, folded, first[:5])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
