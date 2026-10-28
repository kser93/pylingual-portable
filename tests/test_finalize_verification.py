from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pylingual_portable import sessions
from pylingual_portable.toolchain import compile_with_toolchain


class FinalizeVerificationTest(unittest.TestCase):
    def _new_session(
        self,
        root: Path,
        original_source: str,
        candidate_source: str,
    ) -> tuple[str, dict]:
        original = root / "original.py"
        original.write_text(original_source, encoding="utf-8")
        pyc = root / "sample.pyc"
        compile_with_toolchain(original, pyc, "3.12")
        session_id, report = sessions.import_source(pyc, candidate_source, "3.12")
        self.addCleanup(shutil.rmtree, sessions.SESSIONS / session_id, ignore_errors=True)
        return session_id, report

    def _report_path(self, session_id: str) -> Path:
        return sessions.SESSIONS / session_id / "revisions" / "0000" / "report.json"

    def _rewrite_report(self, session_id: str, **changes) -> None:
        path = self._report_path(session_id)
        report = json.loads(path.read_text(encoding="utf-8"))
        report.update(changes)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    def test_stale_perfect_report_is_reverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id, report = self._new_session(root, "x = 1\n", "x = True\n")
            self.assertNotEqual(report["status"], "perfect")

            self._rewrite_report(
                session_id,
                status="perfect",
                summary={"total": 1, "perfect": 1, "syntax_errors": 0, "semantic_errors": 0, "score": 1.0},
                diagnostics=[],
                next_actions=[],
            )
            finalized = sessions.finalize_source(session_id)

            self.assertEqual(finalized["error"], "not_perfect")
            self.assertTrue(finalized["reverified"])
            self.assertFalse((root / "sample.py").exists())

    def test_report_source_hash_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id, report = self._new_session(root, "x = 1\n", "x = 1\n")
            self.assertEqual(report["status"], "perfect")

            self._rewrite_report(session_id, source_sha256="0" * 64)
            finalized = sessions.finalize_source(session_id)

            self.assertEqual(finalized["error"], "source_hash_mismatch")
            self.assertFalse((root / "sample.py").exists())

    def test_changed_original_pyc_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id, report = self._new_session(root, "x = 1\n", "x = 1\n")
            self.assertEqual(report["status"], "perfect")

            (root / "sample.pyc").write_bytes((root / "sample.pyc").read_bytes() + b"\0")
            finalized = sessions.finalize_source(session_id)

            self.assertEqual(finalized["error"], "original_pyc_changed")
            self.assertFalse((root / "sample.py").exists())

    def test_perfect_source_is_reverified_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id, report = self._new_session(root, "x = 1\n", "x = 1\n")
            self.assertEqual(report["status"], "perfect")

            finalized = sessions.finalize_source(session_id)

            self.assertEqual(finalized["status"], "perfect")
            self.assertTrue(finalized["reverified"])
            output = Path(finalized["path"])
            self.assertTrue(output.is_file())
            self.assertEqual(finalized["sha256"], report["source_sha256"])


if __name__ == "__main__":
    unittest.main()
