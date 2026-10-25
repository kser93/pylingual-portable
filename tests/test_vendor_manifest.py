from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_vendor import (  # noqa: E402
    _is_excluded,
    _submodule_head,
    _submodule_urls,
    check_components,
)


class SubmoduleHelpersTest(unittest.TestCase):
    def test_git_file_is_excluded_from_tree_hash(self) -> None:
        self.assertTrue(_is_excluded(Path(".git"), {}))
        self.assertTrue(_is_excluded(Path("pkg/.git"), {}))

    def test_gitmodules_urls_are_read_by_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".gitmodules"
            path.write_text(
                '[submodule "vendor/pylingual"]\n'
                "\tpath = vendor/pylingual\n"
                "\turl = https://github.com/syssec-utd/pylingual\n",
                encoding="utf-8",
            )
            self.assertEqual(
                _submodule_urls(path),
                {"vendor/pylingual": "https://github.com/syssec-utd/pylingual"},
            )

    def test_submodule_head_reads_detached_and_ref_heads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vendor" / "pylingual"
            gitdir = Path(tmp) / ".git" / "modules" / "vendor" / "pylingual"
            root.mkdir(parents=True)
            gitdir.mkdir(parents=True)
            (root / ".git").write_text(
                "gitdir: ../../.git/modules/vendor/pylingual\n", encoding="utf-8"
            )
            commit = "11a1516d84a6c2aa71ec23fbd11e4b99dc8c4a86"
            (gitdir / "HEAD").write_text(commit + "\n", encoding="utf-8")
            self.assertEqual(_submodule_head(root), commit)
            (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (gitdir / "refs" / "heads").mkdir(parents=True)
            (gitdir / "refs" / "heads" / "main").write_text(commit + "\n", encoding="utf-8")
            self.assertEqual(_submodule_head(root), commit)


class ComponentsManifestTest(unittest.TestCase):
    def test_components_pass_submodule_and_tree_checks(self) -> None:
        result = check_components()
        self.assertTrue(result["ok"], result["errors"])
        manifest = json.loads(
            (ROOT / "vendor" / "components.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {name: spec.get("kind") for name, spec in manifest["components"].items()},
            {"pylingual": "git-submodule", "xdis": "git-submodule"},
        )


if __name__ == "__main__":
    unittest.main()
