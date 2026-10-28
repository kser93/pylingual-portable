# PyLingual operational rules

Ruleset version: 1
Applies to: every target version

These rules are process discipline. They are admitted only after a file reached
`status: "perfect"` and was finalized; they describe how to work, not what a
particular binary contained.

## R1. One worker, one file

The MCP server is synchronous and GPU-bound. Run exactly one decompilation at a
time. Parallel `decompile` calls queue behind each other and can exhaust the
server; a crashed server costs more than the queue would have.

## R2. Ground truth before hypotheses

A worker needs the original bytecode, not a summary: constant table in original
order, exception table, names/varnames/cellvars/freevars, and the disassembly
with offsets. `get_code_object` may return a window shorter than the real code
object; never treat it as the whole truth.

## R3. Verify with the same comparator as the server

A local dry-run is only meaningful if it uses the same compiler and the same
comparison semantics as the server: per-code-object instruction equivalence plus
positional `co_consts` and metadata. An approximation produces false negatives
and hides real defects.

## R4. Repair order

Fix in this order: compilation errors, then exception regions (`try`/`except`/
`finally` boundaries), then branch forms (`if`/`elif`/`else`, `break`/`continue`/
`return`), then constant tables, then string/dict payloads, then decorators.
Structural mistakes invalidate everything downstream; constants are the last
mile, not the first.

## R5. Constant order is a first-class target

`co_consts` is compared positionally. The position of `None` is a common
failure. Different source shapes move it: an explicit `return` interns it at
that point, implicit branch exits can defer it to the end, an explicit
`return None` pins it to the branch. Choose the shape deliberately and verify
the whole table, not just the value set.

## R6. No dead code, no placeholders

Never introduce `if False:`, `while False:`, unreachable padding, dummy
statements, or placeholder literals to influence the compiler. Such a revision
is invalid even if it happens to verify. If a technique requires unreachable
code, the technique is wrong.

## R7. Reindentation and literals

A global dedent/indent also changes the content of multi-line string literals.
After any block-level reindentation, re-check every multi-line literal and every
string constant. Code indentation and literal indentation are different things.

## R8. Decorators in one pass

The fallback decompiler can duplicate, drop, or misplace decorators. Scan the
whole class body once: remove consecutive identical duplicates, restore missing
decorators with their exact argument types, and compare the class-body bytecode
rather than fixing them one by one.

## R9. Dictionaries are built, not typed

Dict literals compile to ordered key tuples, `BUILD_CONST_KEY_MAP`, and
`DICT_UPDATE` for `**` groups. Reconstruct the key order and the unpacking
boundaries from the bytecode; a visually equal dict with a different order is a
different constant table.

## R10. Unreachable statements still move offsets

A statement under a `return` is dropped by the compiler; the missing instruction
shifts every later offset and the exception-table start. If the verifier reports
an offset or control-flow mismatch near a block boundary, look for a dedented
statement that should be live.

## R11. One hypothesis, one revision, one minimal check

Change one code object per revision. Before declaring a defect unreproducible,
test the construct on a minimal example with the target compiler. "Impossible"
is a conclusion about the compiler, and it must be demonstrated, not assumed.

## R12. Transfer large sources byte-exact

`apply_patch` takes the complete source. For large files do not retype it:
stream the bytes from disk and pass them through, then compare SHA-256 on both
sides (the file, the request, and the finalized output). A single altered
character invalidates the revision.

## R13. Journal the hypothesis and the bytecode effect

A journal entry that only counts failures cannot be reused. Record: the failing
code object, the hypothesis, the source shape before/after, and the bytecode
effect (const index, exception entry, offset, NOP). Provenance stays in the
local journal; reusable rules are written without it.
