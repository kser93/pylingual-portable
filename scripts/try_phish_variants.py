from __future__ import annotations

from pathlib import Path

from pylingual.editable_bytecode import PYCFile
from pylingual_portable.toolchain import compile_with_toolchain


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "workspace" / "sessions" / "ses_02277b8be62a4f30" / "revisions" / "0003" / "source.py"
TMP = ROOT / "workspace" / "tmp" / "phish_variants"
OLD = "    phishy_word_found, benign_word_found, unique_word_count, text_length = (0, 0, 0, 0)"
VARIANTS = {
    "parens": OLD,
    "no_parens": "    phishy_word_found, benign_word_found, unique_word_count, text_length = 0, 0, 0, 0",
    "repeat": "    phishy_word_found, benign_word_found, unique_word_count, text_length = (0,) * 4",
    "chained": "    phishy_word_found = benign_word_found = unique_word_count = text_length = 0",
}


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    if OLD not in source:
        print("source pattern not found")
        return 2
    TMP.mkdir(parents=True, exist_ok=True)
    for name, line in VARIANTS.items():
        path = TMP / f"{name}.py"
        path.write_text(source.replace(OLD, line, 1), encoding="utf-8")
        pyc = TMP / f"{name}.pyc"
        compile_with_toolchain(path, pyc, "3.6")
        pyc_file = PYCFile(pyc)
        target = next((bc for bc in pyc_file.iter_bytecodes() if bc.name == "<module>.pdf_feature_extraction"), None)
        print("===", name)
        if target is None:
            print("not found")
            continue
        for index, inst in enumerate(target.instructions[:12]):
            print(index, inst.opname, inst.argval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
