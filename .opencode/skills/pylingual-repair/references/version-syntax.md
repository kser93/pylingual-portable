# Target-version syntax constraints

The source you submit is compiled by the **target** CPython toolchain, not by
the runtime Python. The exact verifier will reject syntax that the target does
not understand. Use this as a guardrail; the target compiler is the final
authority.

| Target | Safe to use | Do not introduce |
| --- | --- | --- |
| 3.6 | f-strings, variable annotations, `async`/`await`, underscores in numeric literals | `:=`, positional-only `/`, `dataclasses` as stdlib, `from __future__ import annotations` |
| 3.7 | 3.6 features, `dataclasses`, `from __future__ import annotations`, `breakpoint()` | `:=`, positional-only `/` |
| 3.8 | 3.7 features, walrus `:=`, positional-only `/`, f-string `=` | `list[int]` as a runtime annotation (use `typing.List`), dict union `|` |
| 3.9 | 3.8 features, built-in generics `list[int]`, dict union `|`, `removeprefix`/`removesuffix` | `match`, `X | Y` as a type union in annotations |
| 3.10 | 3.9 features, structural pattern matching, `X | Y` type unions, parenthesized context managers | `except*`, PEP 695 type parameters |
| 3.11 | 3.10 features, `except*`, exception groups, `tomllib`, `typing.Self`, `TaskGroup` | PEP 695 type parameter syntax |
| 3.12 | 3.11 features, PEP 695 `type` aliases and `def f[T]`/`class C[T]`, new f-string grammar, `typing.override` | t-strings |
| 3.13 | 3.12 features, type-parameter defaults, `copy.replace`, `typing.ReadOnly` | t-strings |
| 3.14 | 3.13 features plus that version’s documented syntax changes (for example template strings and deferred annotation behavior) | syntax introduced only in 3.15 |
| 3.15 | only syntax the installed 3.15 toolchain accepts | syntax from a later version |

## Practical rules

- When repairing an older target, prefer the oldest widely supported form that
  produces the same bytecode. A `typing.Optional[str]` annotation and
  `str | None` are not interchangeable on Python 3.9.
- Do not add `from __future__ import annotations` unless the original module
  had it or the target supports it; it changes annotation evaluation and can
  change bytecode.
- Do not add `match` for a target below 3.10, `except*` below 3.11, or PEP 695
  type parameters below 3.12.
- Do not add t-strings for a target below 3.14.
- Do not “modernize” f-strings, comprehensions, or annotations while repairing.
  The goal is bytecode equivalence, not current style.
- If a syntax fix is needed, isolate it in its own revision so a syntax error
  is not confused with a semantic regression.
- For 3.6/3.7, avoid f-string debug syntax (`f"{x=}"`), walrus, and
  positional-only markers.
- For 3.6, `dataclasses` is not in the standard library; removing an import can
  change module-level bytecode significantly.
- For 3.8+, the compiler may constant-fold differently; preserve constants and
  expression shape when the disassembly shows a folded value.
- For 3.11+, exception handling is encoded in the exception table. Do not infer
  syntax version from `SETUP_*` opcodes alone.
- For 3.12+, comprehensions and f-strings may compile differently than older
  versions; use the target disassembly.
- For 3.14/3.15, verify unfamiliar syntax with the target toolchain before
  sending a large patch. A failed compile is still a recorded revision.
