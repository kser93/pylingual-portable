---
name: PyLingual Repair
description: Exact-verification workflow for decompiling Python .pyc files and repairing failing code objects with the PyLingual MCP tools
---

# PyLingual Repair

Use this skill for every PyLingual decompilation or repair task. The goal is not
to produce readable-looking source; the goal is to make the target CPython
compiler produce bytecode that exactly matches the original `.pyc`.

## Tool boundary

PyLingual is the only allowed decompiler. Do not install, download, invoke,
compare with, or check the availability of `uncompyle6`, `decompyle3`, `pycdc`,
`pycdas`, `unpyc`, or any other decompiler/bytecode-to-source tool. Do not use
`pip`, package indexes, Git, web search, or web fetch to find alternatives. A
failed PyLingual result is an input to the repair loop, not a reason to switch
tools. If the environment does not provide a needed PyLingual feature, report
that limitation instead of installing something else.

## 1. Start and triage

- `.pyc` input: call `pylingual_decompile` with `path`; pass `version` only when
  it is explicitly known. If it is unknown, omit the argument and let the server
  detect it; never guess. The result already contains revision 0 and a
  verification report.
- `ses_...` input: call `pylingual_get_session`, then continue at its current
  revision.
- Call `pylingual_get_report` with `detail: "compact"` first. Use
  `detail: "summary"` for a large file, and `detail: "full"` only when you need
  the complete code-object table.
- Read, in this order: `status`, `summary`, `remaining`, `diagnostics`,
  `next_actions`.
- If `status` is `"perfect"`, do not “improve” it. Call
  `pylingual_finalize` to write `.py` beside the original `.pyc`, then stop.
- If `status` is `"syntax_error"`, fix compilation before semantic work.

## 2. Select one target

Prefer failures in this order:

1. syntax errors;
2. leaf functions over module-level code;
3. diagnostics with a concrete `line`/`offset`;
4. the smallest source region;
5. the failure whose fix is most likely to be local.

Do not try to fix multiple independent code objects in one revision. A revision
must be attributable to one hypothesis.

## 3. Build context

For the chosen code object:

- call `pylingual_get_code_object` with its `code_object_id`;
- read `source_slice` and the original `bytecode`;
- note `first_line`, failure `line`, and failure `offset`;
- compare the original instructions with the candidate source, not with the
  previous candidate’s pretty formatting.

Then call `pylingual_get_source` once and keep the full source for patch
construction. Do not repeatedly fetch it.

Useful bytecode questions:

- Which branch target does a `POP_JUMP_IF_*` use?
- Is the loop a `FOR_ITER` or a `JUMP_BACKWARD` + condition loop?
- Which exception region covers the failing instruction?
- Is a value loaded with `LOAD_FAST`, `LOAD_DEREF`, `LOAD_GLOBAL`, or
  `LOAD_ATTR`?
- Is the call a normal call, method call, keyword call, or `CALL_FUNCTION_EX`?
- Is the result stored with `STORE_FAST`, `STORE_DEREF`, `STORE_ATTR`, or
  `STORE_SUBSCR`?
- Are constants (`RETURN_CONST`, `LOAD_CONST`) different, including `None`,
  strings, tuples, and docstrings?

## 4. Patch

Call `pylingual_apply_patch` with the complete source and the exact current
`base_revision`. The server recompiles with the target toolchain and runs exact
bytecode comparison. A patch is not accepted because it looks right.

Response handling:

- `status: "perfect"` — call `pylingual_finalize` and stop.
- `status: "syntax_error"` — read the compiler message, fix it, and resubmit.
  This counts as a revision.
- `regressed` non-empty — inspect `regressed` and `progress`. If the net perfect
  count did not increase, revert to the parent. If it did increase, repair the
  regression before continuing.
- `fixed` non-empty — keep the patch and continue.
- `base_revision_mismatch` — call `get_session`, use the reported current
  revision, and resubmit. Never guess a revision.
- `remaining` — use these IDs for the next iteration; do not re-derive them
  from the whole report.

Do not use `pylingual_verify_source` for every iteration. It is a dry run; use
it only when you deliberately want to test before creating a revision.

## 5. Common repair hypotheses

### Conditions and comparisons

- Inverted branch: swap `if`/`else` or negate the condition.
- Wrong comparison: `==` vs `is`, `<` vs `<=`, `in` vs `not in`.
- Boolean structure: `and`/`or`, short-circuit order, chained comparisons.
- `if x:` vs `if x is not None:` changes the truth test and bytecode.
- A conditional expression may have been flattened into statements, or the
  reverse. Follow the jump targets.

### Loops

- `for` vs `while`; `range` boundaries; `else` on loops.
- `break`/`continue` placed in the wrong branch.
- Accumulator initialization before the loop.
- `for ... in enumerate(...)` vs manual index increments.
- Comprehension vs explicit loop; generator vs list comprehension.

### Functions and calls

- Wrong parameter order, default values, `*args`/`**kwargs`.
- Keyword vs positional calls; `CALL` flags and `KW_NAMES`.
- Decorator order or a missing decorator call.
- Closure cells: `LOAD_DEREF`/`STORE_DEREF`, `COPY_FREE_VARS`,
  `MAKE_CELL`, `LOAD_CLOSURE`.
- A method call on the wrong receiver; `LOAD_METHOD` vs `LOAD_ATTR`.

### Classes

- Base-class order; metaclass keyword.
- Class-body vs method-body scope.
- Property/staticmethod/classmethod decorators.
- `super()` call shape and zero-argument super.
- Descriptor or `__slots__` differences.

### Exceptions

- `try`/`except`/`else`/`finally` block boundaries.
- Exception tuple vs single exception; bare `except` vs `except Exception`.
- Re-raise vs return in the handler.
- Suppression/cleanup order in `finally`.
- In 3.11+, exception-table regions are authoritative; do not infer handler
  layout from indentation alone.

### Modules and constants

- Import form (`import x` vs `from x import y`) and aliasing.
- Module-level execution order.
- Mutable default arguments and constant folding.
- Docstrings and `__doc__` constants.
- `__all__`, `__name__`, and annotation-related code objects.

## 6. Context budget

- Keep one failing code object in focus.
- Request compact reports; request full source only for patching.
- Do not repeat `get_session` after every patch; the patch result includes the
  new revision and delta.
- Do not dump disassembly for perfect code objects.
- If a response is truncated, request a narrower code object, not the whole
  report again.

## 7. Stop conditions

Stop when any of these is true:

- `status: "perfect"`;
- the remaining failure cannot be fixed without violating the target version’s
  syntax or the original semantics;
- the MCP server reports an unrecoverable toolchain/model error.

There is no fixed patch budget and no partial-success outcome. If the host step
or context limit is reached, return `failed` with the last revision, remaining
code-object IDs, and attempted strategies. The orchestrator starts a fresh
worker on the same file; it does not skip the file and does not accept partial
success.

If a non-perfect revision is returned, do not call `pylingual_finalize`; the
target `.py` must not be presented as a successful recovery.

## References

- `references/tool-contract.md` — exact tool arguments, result fields, and
  revision semantics.
- `references/repair-patterns.md` — more detailed bytecode-to-source patterns.
- `references/version-syntax.md` — syntax constraints for Python 3.6–3.15.
