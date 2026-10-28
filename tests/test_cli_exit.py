from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import patch

from pylingual_portable import cli


class _FakeResult:
    def __init__(self, rate: float) -> None:
        self.equivalence_results = [object()] if rate == 1.0 else []
        self.decompiled_source = "x = 1\n"
        self._rate = rate

    def calculate_success_rate(self) -> float:
        return self._rate


class CliExitTest(unittest.TestCase):
    def test_non_perfect_decompile_returns_nonzero(self) -> None:
        with patch("pylingual_portable.cli.decompile_file", return_value=_FakeResult(0.5)):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = cli.main(["decompile", "sample.pyc"])
        self.assertEqual(code, 1)

    def test_perfect_decompile_returns_zero(self) -> None:
        with patch("pylingual_portable.cli.decompile_file", return_value=_FakeResult(1.0)):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = cli.main(["decompile", "sample.pyc"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
