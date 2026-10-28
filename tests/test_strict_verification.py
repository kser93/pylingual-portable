from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pylingual_portable import sessions
from pylingual_portable.strict_verification import compare_pyc_strict
from pylingual_portable.toolchain import compile_with_toolchain


class StrictVerificationTest(unittest.TestCase):
    def test_constant_type_mismatch_is_not_perfect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.py"
            candidate = root / "candidate.py"
            original.write_text("x = 1\n", encoding="utf-8")
            candidate.write_text("x = True\n", encoding="utf-8")
            original_pyc = root / "original.pyc"
            candidate_pyc = root / "candidate.pyc"
            compile_with_toolchain(original, original_pyc, "3.12")
            compile_with_toolchain(candidate, candidate_pyc, "3.12")

            results = compare_pyc_strict(original_pyc, candidate_pyc)

            self.assertTrue(results)
            self.assertFalse(all(result.success for result in results))

    def test_signature_mismatch_is_not_perfect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.py"
            candidate = root / "candidate.py"
            original.write_text("def f(a):\n    return a\n", encoding="utf-8")
            candidate.write_text("def f(a, b):\n    return a\n", encoding="utf-8")
            original_pyc = root / "original.pyc"
            candidate_pyc = root / "candidate.pyc"
            compile_with_toolchain(original, original_pyc, "3.12")
            compile_with_toolchain(candidate, candidate_pyc, "3.12")

            results = compare_pyc_strict(original_pyc, candidate_pyc)

            self.assertTrue(results)
            self.assertFalse(all(result.success for result in results))

    def test_identical_source_is_perfect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.py"
            source.write_text("def f(a):\n    return a\n", encoding="utf-8")
            original_pyc = root / "original.pyc"
            candidate_pyc = root / "candidate.pyc"
            compile_with_toolchain(source, original_pyc, "3.12")
            compile_with_toolchain(source, candidate_pyc, "3.12")

            results = compare_pyc_strict(original_pyc, candidate_pyc)

            self.assertTrue(results)
            self.assertTrue(all(result.success for result in results))

    def test_session_verification_uses_strict_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "original.py"
            source.write_text("x = 1\n", encoding="utf-8")
            pyc = root / "original.pyc"
            compile_with_toolchain(source, pyc, "3.12")

            session_id, report = sessions.import_source(pyc, "x = True\n", "3.12")
            try:
                self.assertNotEqual(report["status"], "perfect")
            finally:
                session_dir = sessions.SESSIONS / session_id
                if session_dir.exists():
                    import shutil

                    shutil.rmtree(session_dir)


if __name__ == "__main__":
    unittest.main()
