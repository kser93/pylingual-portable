schema: pylingual/patching/v1
applies_to: "3.11"
ruleset_version: 1
compiler_notes: "original binaries may come from 3.11 alpha builds; the verifier compiles with 3.11.17"

# CPython 3.11 patching techniques

A technique is a hypothesis about a source shape that reproduces the original
bytecode. It is never a guarantee: only the exact verifier decides. Techniques
from other versions are valid hypotheses here as well; the delivery tool returns
them together with this list.

## Build caveats (3.11 alpha vs 3.11 final)

- `None` interning: an alpha build can append the `None` used by bare returns to
  the end of `co_consts`, while a final build interns it at the first return.
- Method calls: an alpha build may emit `LOAD_ATTR` + `CALL`, a final build
  `LOAD_METHOD`. Raw bytes differ, normalized instructions match.
- Annotations: name/type tables may be a flat tuple in one build and separate
  string constants in the other; `LOAD_NAME` versus `LOAD_CONST` for the same
  annotation name is expected.
- `KW_NAMES`: the constant index differs even when the call is identical.
- Inline cache sizes changed between builds: equal normalized instructions can
  have different `co_code` lengths.
- NOP padding and `EXTENDED_ARG` shift offsets and exception boundaries; compare
  after removing them.

## Techniques

### R-3.11-001 · try-header-restore
**symptom:** syntax error at an `except`/`finally` with no `try`, or after a
fallback-reconstructed block.
**change:** restore the missing `try:` at the level indicated by the handler and
dedent or indent the handler body to match.
**effect:** the exception table gains the missing entry with the correct
start/end/target; compilation succeeds.
**verify:** `get_report` shows the object's exception entry equal.

### R-3.11-002 · try-scope-start
**symptom:** exception entry start differs by a few bytes, or the first guarded
instruction is outside the region.
**change:** move `try:` up or down so it starts at the instruction the original
entry starts at (often a `NOP` marker); keep the handler attached.
**effect:** entry `start` matches; no instruction changes elsewhere.
**verify:** exception entries compared as offsets.

### R-3.11-003 · handler-break-not-pass
**symptom:** control-flow mismatch in a loop whose exception handler ends the
iteration.
**change:** the handler body is `break`, not `pass` or `return`, when the
original leaves the loop.
**effect:** replaces a fallthrough with a backward/forward jump to the loop exit.
**verify:** control-flow graph equivalence.

### R-3.11-004 · continue-after-generic-except
**symptom:** the loop body after a broad handler is treated as reachable when it
should restart the iteration.
**change:** add `continue` at the end of the generic handler.
**effect:** adds the backward jump to the loop head.
**verify:** instruction stream equality after jump normalization.

### R-3.11-005 · else-vs-early-return
**symptom:** a block is emitted as `else:` after a branch that already returns.
**change:** flatten to an early `return` followed by the block at the outer
level, or restore the `else` when the original jumps over it.
**effect:** changes `JUMP_FORWARD`/fallthrough shape without changing values.
**verify:** control-flow equivalence plus exact instructions.

### R-3.11-006 · condition-inversion
**symptom:** a guard tests the opposite of the original, or `and`/`or` order is
swapped.
**change:** invert to the form the jumps imply, e.g. `not A or B` instead of
`A and B`, or `not A and not B` instead of `not (A or B)`.
**effect:** the `POP_JUMP_*` pair and its targets match; no extra instructions.
**verify:** jump targets compared as instruction indices.

### R-3.11-007 · const-order-explicit-return
**symptom:** `co_consts` mismatch where the original has `None` earlier than the
candidate.
**change:** add an explicit `return` at the end of the branch where the original
returns.
**effect:** `None` is interned at that point and moves earlier in `co_consts`;
instruction count may stay the same because the return was already implicit.
**verify:** positional `co_consts` equality.

### R-3.11-008 · const-order-implicit-exits
**symptom:** `co_consts` mismatch where the original has `None` last and the
candidate has it at the first return.
**change:** replace sequential `if` statements with explicit `return` by a
single `if/elif` chain with implicit exits at the end of the function.
**effect:** the compiler still emits `LOAD_CONST None; RETURN_VALUE` at the end
of each branch, but interns `None` after all literals, so it lands at the end of
`co_consts`; instruction stream is preserved.
**verify:** positional `co_consts` and instruction equality.

### R-3.11-009 · const-order-return-none
**symptom:** a single code object differs only by the position of `None`.
**change:** make the branch return explicitly (`return None`) where the original
pins the constant, or remove the explicit value where it should be deferred.
**effect:** changes when `None` is interned without changing the value flow.
**verify:** positional `co_consts`.

### R-3.11-010 · const-order-break-instead-of-return
**symptom:** the original has an early exit that is a `RETURN` but the constant
table requires a later `None`.
**change:** when the surrounding control flow allows it, exit the loop with
`break` and place the function return after it.
**effect:** keeps the values and the exit path, changes which statement interns
`None`; no dead code.
**verify:** instruction stream plus `co_consts`.

### R-3.11-011 · dict-key-map-and-update
**symptom:** a dictionary literal has the right keys but the wrong order, or a
`**` group is missing.
**change:** rebuild the literal in the key order of the original key tuple and
split trailing unpacked groups into `**{...}` at the correct boundary.
**effect:** `BUILD_CONST_KEY_MAP` key tuple matches; `DICT_UPDATE` appears at
the right point.
**verify:** constant table and instruction sequence.

### R-3.11-012 · join-fragments
**symptom:** a long assembled string is empty, truncated, or differs only in
internal newlines.
**change:** rebuild it as `''.join([...])` with the exact fragments and their
interpolation points; keep fragment boundaries where the original builds them.
**effect:** the resulting string constant is byte-equal, including whitespace.
**verify:** const equality (exact text).

### R-3.11-013 · literal-indent-preserved
**symptom:** after reindenting a block, string constants lose or gain leading
spaces on continuation lines.
**change:** restore the literal content independently of code indentation; the
closing delimiter's indentation is part of the string.
**effect:** string constants return to their original bytes.
**verify:** const equality per literal.

### R-3.11-014 · decorator-dedup-and-restore
**symptom:** class-body bytecode has an extra decorator call, or a function that
should be decorated has none.
**change:** remove consecutive identical decorators; restore the missing one
with the exact argument types in the original order.
**effect:** class-body call sequence (`LOAD_NAME`, `CALL`, `MAKE_FUNCTION`)
matches; function code object unchanged.
**verify:** class-body instruction equality.

### R-3.11-015 · matrix-row-and-kwargs
**symptom:** a list/matrix literal has one element fewer, or call keyword values
are shifted by one position.
**change:** restore the missing row/element (`BUILD_LIST` arity) or realign the
keyword values to their names.
**effect:** `BUILD_LIST`/`BUILD_CONST_KEY_MAP` arity and const order match.
**verify:** instruction and constant equality.

### R-3.11-016 · unreachable-await-dedent
**symptom:** an offset/exception-start mismatch of a few bytes near a loop or a
`with` block; one `NOP` missing in the candidate.
**change:** find the statement left under a `return` and dedent it to the live
block level.
**effect:** the compiler emits the missing instruction, restoring the `NOP`,
offsets, and the exception entry start.
**verify:** exception entries and instruction offsets.

### R-3.11-017 · module-level-phantom-else
**symptom:** the module's control flow differs by a jump around the whole body;
everything after a guard is indented one level deeper than the original.
**change:** remove the phantom `else:` and dedent the module body; keep the guard
as a plain early `raise`/`return`.
**effect:** removes the jump and restores top-level statement order.
**verify:** module code-object control flow.

### R-3.11-018 · comprehension-restore
**symptom:** a loop and an accumulator replace what should be a comprehension,
or the decompiler emitted a plain loop.
**change:** restore the list/dict/generator comprehension with the original
iteration order and filter.
**effect:** `MAKE_FUNCTION` for the implicit scope, `GET_ITER`, and the
comprehension code object match.
**verify:** nested code-object tree and instructions.

### R-3.11-019 · global-declarations
**symptom:** a name is stored as a local in the candidate but as a module global
in the original.
**change:** add the missing `global` declaration at the top of the function.
**effect:** `STORE_GLOBAL` instead of `STORE_FAST`; `co_names` matches.
**verify:** instruction opnames and names.

### R-3.11-020 · return-outside-try
**symptom:** the exception entry extends past the last real statement, or the
trailing return is inside the guarded region.
**change:** move the trailing `return` outside the `try` so the region ends
before it.
**effect:** exception entry end matches; no change to the returned value.
**verify:** exception entries.
