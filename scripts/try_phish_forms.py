from __future__ import annotations

from pathlib import Path

from pylingual.editable_bytecode import PYCFile
from pylingual_portable.toolchain import compile_with_toolchain


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "workspace" / "sessions" / "ses_02277b8be62a4f30" / "revisions" / "0003" / "source.py"
TMP = ROOT / "workspace" / "tmp" / "phish_forms"
OLD = "    phishy_word_found, benign_word_found, unique_word_count, text_length = (0, 0, 0, 0)"
VARIANTS = {
    "if_true": "    phishy_word_found, benign_word_found, unique_word_count, text_length = (0, 0, 0, 0) if True else (1, 2, 3, 4)",
    "or_tuple": "    phishy_word_found, benign_word_found, unique_word_count, text_length = (0, 0, 0, 0) or (1, 2, 3, 4)",
    "debug": "    phishy_word_found, benign_word_found, unique_word_count, text_length = (0, 0, 0, 0) if __debug__ else (1, 2, 3, 4)",
    "plus_empty": "    phishy_word_found, benign_word_found, unique_word_count, text_length = (0, 0, 0, 0) + ()",
    "star": "    phishy_word_found, benign_word_found, unique_word_count, text_length = (0, 0, 0, 0)[:]",
}


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    if OLD not in source:
        print("pattern not found")
        return 2
    TMP.mkdir(parents=True, exist_ok=True)
    for name, line in VARIANTS.items():
        path = TMP / f"{name}.py"
        path.write_text(source.replace(OLD, line, 1), encoding="utf-8")
        pyc = TMP / f"{name}.pyc"
        compile_with_toolchain(path, pyc, "3.6")
        target = next((bc for bc in PYCFile(pyc).iter_bytecodes() if bc.name == "<module>.pdf_feature_extraction"), None)
        print("===", name)
        if target is None:
            print("not found")
            continue
        print([(inst.opname, str(inst.argval)) for inst in target.instructions[:10]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
