from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_vendor  # noqa: E402
from check_vendor import (  # noqa: E402
    _is_excluded,
    _submodule_head,
    _submodule_urls,
    check_components,
    tree_hash,
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
            (gitdir / "refs" / "heads" / "main").unlink()
            (gitdir / "packed-refs").write_text(
                "# pack-refs with: peeled fully-peeled sorted\n"
                f"{commit} refs/heads/main\n",
                encoding="utf-8",
            )
            self.assertEqual(_submodule_head(root), commit)

    def test_gitlink_parser(self) -> None:
        commit = "11a1516d84a6c2aa71ec23fbd11e4b99dc8c4a86"
        output = f"160000 commit {commit}\tvendor/pylingual\n"
        self.assertEqual(
            check_vendor._gitlink_from_ls_tree(output, "vendor/pylingual"), commit
        )
        self.assertIsNone(
            check_vendor._gitlink_from_ls_tree(output, "vendor/other")
        )

    def test_tree_hash_detects_tracked_pyc_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "fixture.pyc"
            fixture.write_bytes(b"header\x00\x01\x02")
            spec = {"exclude_dirs": [".git"], "exclude_globs": []}
            original, count = tree_hash(root, spec)
            fixture.write_bytes(b"header\x00\x01\x03")
            changed, changed_count = tree_hash(root, spec)
            self.assertEqual((count, changed_count), (1, 1))
            self.assertNotEqual(original, changed)


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

    def test_xdis_hashes_tracked_pyc_fixtures(self) -> None:
        result = check_components()
        self.assertTrue(result["ok"], result["errors"])
        xdis = result["components"]["xdis"]
        self.assertEqual(xdis["files"], 1380, "all tracked xdis files must be hashed")

    def test_update_does_not_write_manifest_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "vendor" / "pylingual").mkdir(parents=True)
            manifest = root / "vendor" / "components.json"
            original = json.dumps(
                {
                    "schema": 1,
                    "algorithm": "sha256-tree-v1",
                    "verified_at": "2026-10-25",
                    "components": {
                        "pylingual": {
                            "path": "vendor/pylingual",
                            "kind": "git-submodule",
                            "upstream": "https://github.com/syssec-utd/pylingual",
                            "version": "0.1.0",
                            "commit": "11a1516d84a6c2aa71ec23fbd11e4b99dc8c4a86",
                            "license": "GPL-3.0-only",
                            "license_file": "vendor/pylingual/LICENSE",
                            "patches": [],
                            "exclude_dirs": [],
                            "exclude_globs": [],
                            "tree_sha256": "0" * 64,
                            "file_count": 1,
                        }
                    },
                },
                indent=2,
            ) + "\n"
            manifest.write_text(original, encoding="utf-8")
            old_root, old_manifest = check_vendor.ROOT, check_vendor.MANIFEST
            check_vendor.ROOT, check_vendor.MANIFEST = root, manifest
            try:
                result = check_components(update=True)
            finally:
                check_vendor.ROOT, check_vendor.MANIFEST = old_root, old_manifest
            self.assertFalse(result["ok"])
            self.assertEqual(manifest.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
