"""Strict post-check for upstream PyLingual PYC comparison.

Upstream ``compare_pyc`` compares instructions and the exception table but does
not compare several code-object metadata fields (most notably ``co_argcount``)
and compares constants with ``==``.  That allows semantically different code
such as ``x = 1`` vs ``x = True`` or ``def f(a)`` vs ``def f(a, b)`` to be
reported as equal.  The portable wrapper keeps upstream source untouched and
adds this conservative metadata/constant check on top of the existing result.
"""

from __future__ import annotations

import math
from typing import Any

from pylingual.equivalence_check import TestResult, compare_pyc as _original_compare_pyc


_METADATA_FIELDS = (
    "co_name",
    "co_qualname",
    "co_argcount",
    "co_posonlyargcount",
    "co_kwonlyargcount",
    "co_flags",
    "co_varnames",
    "co_names",
    "co_cellvars",
    "co_freevars",
)


def _is_code(value: Any) -> bool:
    return hasattr(value, "co_code") and hasattr(value, "co_name")


def _strict_float_equal(left: float, right: float) -> bool:
    if math.isnan(left) and math.isnan(right):
        return True
    if left != right:
        return False
    return math.copysign(1.0, left) == math.copysign(1.0, right)


def _strict_complex_equal(left: complex, right: complex) -> bool:
    return _strict_float_equal(left.real, right.real) and _strict_float_equal(left.imag, right.imag)


def _strict_value_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if _is_code(left) and _is_code(right):
        # Nested code objects are compared separately by compare_pyc.  Use the
        # name as a cheap identity check so a code object is never accepted in
        # place of a plain constant with the same repr.
        return getattr(left, "co_name", None) == getattr(right, "co_name", None)
    if _is_code(left) or _is_code(right):
        return False
    if isinstance(left, float):
        return _strict_float_equal(left, right)
    if isinstance(left, complex):
        return _strict_complex_equal(left, right)
    if isinstance(left, tuple):
        return len(left) == len(right) and all(
            _strict_value_equal(a, b) for a, b in zip(left, right)
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _strict_value_equal(a, b) for a, b in zip(left, right)
        )
    if isinstance(left, dict):
        if set(left) != set(right):
            return False
        return all(_strict_value_equal(left[key], right[key]) for key in left)
    if isinstance(left, frozenset):
        if len(left) != len(right):
            return False
        remaining = list(right)
        for item in left:
            match = next(
                (index for index, candidate in enumerate(remaining) if _strict_value_equal(item, candidate)),
                None,
            )
            if match is None:
                return False
            remaining.pop(match)
        return True
    return left == right


def _strict_consts_equal(left: tuple[Any, ...], right: tuple[Any, ...]) -> bool:
    if len(left) != len(right):
        return False
    for left_item, right_item in zip(left, right):
        if _is_code(left_item) and _is_code(right_item):
            if getattr(left_item, "co_name", None) != getattr(right_item, "co_name", None):
                return False
            continue
        if _is_code(left_item) or _is_code(right_item):
            return False
        if not _strict_value_equal(left_item, right_item):
            return False
    return True


def _metadata_mismatch(left: Any, right: Any) -> str | None:
    for field in _METADATA_FIELDS:
        left_value = getattr(left, field, None)
        right_value = getattr(right, field, None)
        if field == "co_posonlyargcount" and left_value is None and right_value is None:
            continue
        if left_value != right_value:
            return field
    if not _strict_consts_equal(left.co_consts, right.co_consts):
        return "co_consts"
    return None


def compare_pyc_strict(pyc_a, pyc_b) -> list[TestResult]:
    """Return upstream comparison results with strict metadata/constant checks."""
    results = _original_compare_pyc(pyc_a, pyc_b)
    strict_results: list[TestResult] = []
    for result in results:
        if not getattr(result, "success", False):
            strict_results.append(result)
            continue
        code_a = getattr(result, "bc_a", None)
        code_b = getattr(result, "bc_b", None)
        if code_a is None or code_b is None or code_a is code_b:
            strict_results.append(result)
            continue
        mismatch = _metadata_mismatch(code_a.codeobj, code_b.codeobj)
        if mismatch is None:
            strict_results.append(result)
            continue
        strict_results.append(
            TestResult(
                False,
                f"Different code object metadata: {mismatch}",
                code_a,
                code_b,
                getattr(result, "failed_line_number", None),
                getattr(result, "failed_offset", None),
            )
        )
    return strict_results


compare_pyc_strict._pylingual_portable_strict = True  # type: ignore[attr-defined]
