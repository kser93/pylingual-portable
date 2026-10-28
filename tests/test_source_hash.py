from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from pylingual_portable import sessions


class SourceHashTest(unittest.TestCase):
    def test_atomic_write_text_writes_lf_and_matches_text_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.py"
            source = "a\nb\n"

            sessions.atomic_write_text(path, source)

            self.assertEqual(path.read_bytes(), source.encode("utf-8"))
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                sessions.sha256_text(source),
            )

    def test_finalize_writes_hashable_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "sample.py"
            pyc_path = root / "sample.pyc"
            source = "x = 1\n"
            source_path.write_text(source, encoding="utf-8")
            sessions.compile_with_toolchain(source_path, pyc_path, "3.12")

            session_id, report = sessions.import_source(pyc_path, source, "3.12")
            try:
                self.assertEqual(report["status"], "perfect")
                finalized = sessions.finalize_source(session_id)
                self.assertEqual(finalized["status"], "perfect")
                output = Path(finalized["path"])
                digest = hashlib.sha256(output.read_bytes()).hexdigest()
                self.assertEqual(digest, finalized["sha256"])
                self.assertEqual(digest, report["source_sha256"])
                meta = sessions.get_session(session_id)
                self.assertEqual(meta["finalized"]["path"], str(output))
                self.assertEqual(meta["finalized"]["sha256"], digest)
            finally:
                session_dir = sessions.SESSIONS / session_id
                if session_dir.exists():
                    import shutil

                    shutil.rmtree(session_dir)

    def test_crlf_import_is_normalized_before_hashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "sample.py"
            pyc_path = root / "sample.pyc"
            source_path.write_text("x = 1\n", encoding="utf-8")
            sessions.compile_with_toolchain(source_path, pyc_path, "3.12")

            session_id, report = sessions.import_source(pyc_path, "x = 1\r\n", "3.12")
            try:
                self.assertEqual(report["status"], "perfect")
                revision_source = sessions.SESSIONS / session_id / "revisions" / "0000" / "source.py"
                self.assertEqual(revision_source.read_bytes(), b"x = 1\n")
                finalized = sessions.finalize_source(session_id)
                digest = hashlib.sha256(Path(finalized["path"]).read_bytes()).hexdigest()
                self.assertEqual(digest, report["source_sha256"])
            finally:
                session_dir = sessions.SESSIONS / session_id
                if session_dir.exists():
                    import shutil

                    shutil.rmtree(session_dir)


if __name__ == "__main__":
    unittest.main()
