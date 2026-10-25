from __future__ import annotations

import unittest

from pylingual_portable.upstream import _wrap_run_cflow_reconstruction


class _FakeLine:
    def __init__(self, line: str):
        self.line = line

    def with_line(self, line: str) -> "_FakeLine":
        return _FakeLine(line)


class _FakePyc:
    def __init__(self, timestamp: int | None):
        self.timestamp = timestamp


class _FakeSourceContext:
    def __init__(self) -> None:
        self.header_lines = [
            _FakeLine("# Decompiled with PyLingual"),
            _FakeLine("# Source timestamp: 1970-01-01 00:00:00 UTC (0)"),
        ]


class _FakeDecompiler:
    def __init__(self, timestamp: int | None):
        self.pyc = _FakePyc(timestamp)
        self.source_context = _FakeSourceContext()
        self.calls = 0


def _original(self: _FakeDecompiler) -> None:
    self.calls += 1
    self.source_context.header_lines = [
        _FakeLine(f"# Source timestamp: 1970-01-01 00:00:00 UTC ({self.pyc.timestamp})")
    ]


class TimestampPatchTest(unittest.TestCase):
    def test_none_timestamp_uses_unknown_header(self) -> None:
        decompiler = _FakeDecompiler(None)
        _wrap_run_cflow_reconstruction(_original)(decompiler)

        self.assertEqual(decompiler.calls, 1)
        self.assertIsNone(decompiler.pyc.timestamp)
        self.assertEqual(
            decompiler.source_context.header_lines[0].line,
            "# Source timestamp: unknown (hash-based pyc)",
        )

    def test_real_timestamp_is_untouched(self) -> None:
        decompiler = _FakeDecompiler(123)
        _wrap_run_cflow_reconstruction(_original)(decompiler)

        self.assertEqual(decompiler.calls, 1)
        self.assertEqual(decompiler.pyc.timestamp, 123)
        self.assertEqual(
            decompiler.source_context.header_lines[0].line,
            "# Source timestamp: 1970-01-01 00:00:00 UTC (123)",
        )


if __name__ == "__main__":
    unittest.main()
