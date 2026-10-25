from __future__ import annotations

import unittest

import pylingual.decompiler as decompiler_module

from pylingual_portable import models, toolchain
from pylingual_portable.upstream import assert_contract, install_local_components


class UpstreamContractTest(unittest.TestCase):
    def test_contract(self) -> None:
        result = assert_contract()
        self.assertTrue(result["ok"])
        self.assertIn("pylingual.decompiler.decompile", result["checked"])

    def test_local_components_are_installed(self) -> None:
        install_local_components()
        self.assertIs(decompiler_module.load_models, models.load_models)
        self.assertIs(decompiler_module.compile_version, toolchain.compile_with_toolchain)

    def test_none_timestamp_patch_is_installed(self) -> None:
        install_local_components()
        self.assertTrue(
            getattr(
                decompiler_module.Decompiler.run_cflow_reconstruction,
                "_pylingual_portable_patch",
                False,
            )
        )


if __name__ == "__main__":
    unittest.main()
