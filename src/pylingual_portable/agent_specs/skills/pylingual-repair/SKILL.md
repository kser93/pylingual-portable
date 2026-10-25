# PyLingual repair skill

## Goal

Make the target CPython compiler produce bytecode that exactly matches the
original `.pyc`. A result is accepted only when exact verification reports
`status: "perfect"`.

## Verification

For each candidate source, the server:

1. compiles it with the target-version CPython toolchain;
2. compares bytecode and control flow with the original `.pyc`;
3. returns a report with per-code-object status.

`perfect` means every code object matched. `syntax_error` means the candidate
does not compile. `semantic_error` means the code compiles but differs.

## Repair cycle

```text
decompile
  -> get_report(detail="compact")
  -> if perfect: finalize
  -> select one failing code object
  -> get_code_object
  -> get_source
  -> edit one hypothesis into the complete source
  -> apply_patch(base_revision=current)
  -> inspect fixed/regressed/remaining/progress
  -> repeat until perfect
  -> finalize
```

## Diagnostic priorities

1. Syntax errors.
2. Leaf functions over module-level code.
3. Failures with a concrete line and offset.
4. The smallest source region.
5. The change most likely to be local.

Do not attempt to fix several independent code objects in one revision.
A revision must be attributable to one hypothesis.

## Useful questions

- Which branch target does a `POP_JUMP_IF_*` use?
- Is the loop a `FOR_ITER` or a `JUMP_BACKWARD` plus condition?
- Which exception region covers the failing instruction?
- Is a value loaded with `LOAD_FAST`, `LOAD_DEREF`, `LOAD_GLOBAL`, or
  `LOAD_ATTR`?
- Is the call a normal call, method call, keyword call, or `CALL_FUNCTION_EX`?
- Is the result stored with `STORE_FAST`, `STORE_DEREF`, `STORE_ATTR`, or
  `STORE_SUBSCR`?
- Are constants (`RETURN_CONST`, `LOAD_CONST`) different, including `None`,
  strings, tuples, and docstrings?

## Common hypotheses

- Conditions: inverted branch, wrong comparison, `and`/`or` order, chained
  comparisons.
- Loops: `for` versus `while`, range boundaries, `break`/`continue`, loop
  `else`.
- Calls: parameter order, defaults, keyword versus positional, `*args` and
  `**kwargs`.
- Closures: `LOAD_DEREF`/`STORE_DEREF`, `COPY_FREE_VARS`, `MAKE_CELL`.
- Classes: base order, metaclass keyword, decorators, `super()` shape.
- Exceptions: handler boundaries, exception tuples, `else`/`finally` order.
- Modules: import form, aliases, execution order, docstrings, `__all__`.

## Context discipline

- Keep one failing code object in focus.
- Request a compact report first.
- Fetch the complete source only when constructing a patch.
- Do not dump disassembly for perfect code objects.
- Do not repeatedly call `get_session` after every patch.

## Stop conditions

Stop only when:

- `status: "perfect"`;
- the failure cannot be fixed without violating the target version's syntax or
  the original semantics;
- the server reports an unrecoverable toolchain or model error.

If the host step or context limit is reached, return the last revision,
remaining code-object IDs, and attempted strategies. Do not call `finalize` for
a non-perfect revision.
