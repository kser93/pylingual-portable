from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pylingual_portable import health


ROLES = ("segmenter", "segmenter_tokenizer", "statement", "statement_tokenizer")


def _write_links(path: Path) -> None:
    links = {
        "3.12": {
            role: {
                "repo": f"org/repo-{role}",
                "sha": f"{index + 1:040x}",
                "files": {"model.safetensors": "https://example.invalid/model.safetensors"}
                if role in {"segmenter", "statement"}
                else {"tokenizer.json": "https://example.invalid/tokenizer.json"},
            }
            for index, role in enumerate(ROLES)
        }
    }
    path.write_text(json.dumps(links), encoding="utf-8")


def _create_snapshot(hub: Path, links_path: Path, *, skip_file: bool = False) -> None:
    links = json.loads(links_path.read_text(encoding="utf-8"))
    for version, roles in links.items():
        for role, entry in roles.items():
            snapshot = hub / ("models--" + entry["repo"].replace("/", "--")) / "snapshots" / entry["sha"]
            snapshot.mkdir(parents=True)
            for filename in entry["files"]:
                if skip_file and role == "statement":
                    continue
                (snapshot / filename).write_bytes(b"weights")


class HealthTest(unittest.TestCase):
    def test_missing_snapshot_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            links_path = root / "model-links.json"
            _write_links(links_path)

            result = health.model_status(links_path=links_path, hub=root / "hub")

            self.assertFalse(result["ok"])
            self.assertTrue(result["missing"])
            self.assertEqual(result["models"], [])

    def test_missing_required_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            links_path = root / "model-links.json"
            hub = root / "hub"
            _write_links(links_path)
            _create_snapshot(hub, links_path, skip_file=True)

            result = health.model_status(links_path=links_path, hub=hub)

            self.assertFalse(result["ok"])
            self.assertTrue(any("model.safetensors" in item["missing"] for item in result["missing"]))

    def test_complete_snapshot_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            links_path = root / "model-links.json"
            hub = root / "hub"
            _write_links(links_path)
            _create_snapshot(hub, links_path)

            result = health.model_status(links_path=links_path, hub=hub)

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["models"], ["3.12"])

    def test_toolchain_status_detects_missing_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for version in ("3.6", "3.7"):
                directory = root / f"cpython-{version}.1-win-x64"
                directory.mkdir()
                (directory / "python.exe").write_bytes(b"exe")

            result = health.toolchain_status(
                toolchains_dir=root,
                expected=("3.6", "3.7", "3.12"),
            )

            self.assertFalse(result["ok"])
            self.assertEqual(result["missing"], ["3.12"])


if __name__ == "__main__":
    unittest.main()
