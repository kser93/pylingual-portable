from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


class RepoHygieneTest(unittest.TestCase):
    def setUp(self) -> None:
        probe = _git("rev-parse", "--is-inside-work-tree")
        if probe.returncode != 0:
            self.skipTest("not a Git worktree")

    def test_workspace_is_not_tracked(self) -> None:
        result = _git("ls-files", "workspace")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_generated_paths_are_ignored(self) -> None:
        candidates = (
            "workspace/sessions/ses_0000000000000000/session.json",
            "workspace/exports/example.py",
            "harness/fixtures/pyc/3.12/arithmetic.py",
            "models/installed.json",
        )
        for path in candidates:
            result = _git("check-ignore", "-q", path)
            self.assertEqual(result.returncode, 0, f"not ignored: {path}")
            tracked = _git("ls-files", path)
            self.assertEqual(tracked.returncode, 0, tracked.stderr)
            self.assertEqual(tracked.stdout.strip(), "", f"tracked despite ignore rule: {path}")


if __name__ == "__main__":
    unittest.main()
