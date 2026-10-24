# Bytecode-to-source repair patterns

Use the actual disassembly from `pylingual_get_code_object`; the patterns below
are hypotheses, not proof. The exact verifier decides.

## Read the failure first

A typical diagnostic is `Different bytecode` with `line`, `offset`, and a
code-object name. Reconstruct the smallest source region that produces the
instructions around that offset. Then compare:

- operand order;
- branch direction and target;
- constant values and types;
- local/cell/global name kind;
- call convention;
- exception-region boundaries;
- instruction sequence length.

## Conditions

| Symptom | Likely source |
| --- | --- |
| Opposite `POP_JUMP_IF_TRUE` / `POP_JUMP_IF_FALSE` target | `if`/`else` swapped or condition negated |
| `COMPARE_OP` differs | `==`, `!=`, `<`, `<=`, `>`, `>=`, `is`, `is not`, `in`, `not in` changed |
| Short-circuit jump order differs | `a and b` vs `b and a`, or `or` vs `and` |
| `TO_BOOL` or truth test differs | `if x:` vs `if x is not None:` / `if bool(x):` |
| Chained comparison shape differs | `a < b < c` vs `(a < b) and (b < c)` |
| `UNARY_NOT` present/absent | `not` applied at a different level |
| `LOAD_CONST None` vs missing return | implicit `return None` vs explicit `return None` is usually equivalent, but not always in generated code |

For a conditional expression, identify both result values and the jump over
the false arm. For statement `if`, identify the block boundaries and the jump
to the join point.

## Loops

| Symptom | Likely source |
| --- | --- |
| `FOR_ITER` vs `JUMP_BACKWARD` + compare | `for` vs `while` |
| `GET_ITER` / `FOR_ITER` argument differs | iterable expression or `range` shape |
| Jump exits early | `break` placement |
| Jump to loop head skips tail | `continue` placement |
| Loop counter stored before body | accumulator/index initialization |
| Extra `LOAD_FAST`/`STORE_FAST` in body | manual index vs `enumerate` |
| `FOR_ITER` + `END_FOR`/cleanup differs | loop `else` or comprehension |

Check whether the loop body updates the same variable the condition tests. A
`while` loop often has the condition at the bottom or top depending on whether
it is a `while True` with an internal break.

## Functions and closures

| Symptom | Likely source |
| --- | --- |
| `LOAD_DEREF` instead of `LOAD_FAST` | closure variable; use `nonlocal`/outer binding |
| `COPY_FREE_VARS` / `MAKE_CELL` mismatch | closure cell layout or `nonlocal` |
| `LOAD_CLOSURE` tuple differs | nested function captures different names |
| `CALL` argument count/order differs | parameter order or call-site order |
| `KW_NAMES` differs | keyword names in call |
| `CALL_FUNCTION_EX` | `*args` / `**kwargs` |
| `MAKE_FUNCTION` flags differ | defaults, annotations, closure, `__qualname__` |
| `RETURN_VALUE` vs `RETURN_CONST` | constant return or expression |
| `YIELD_VALUE` / `SEND` | generator vs normal function |
| `GET_AWAITABLE` / `SEND` / `END_ASYNC_FOR` | async function or `await` placement |
| `LOAD_METHOD` vs `LOAD_ATTR` | method call vs attribute access |

A closure bug often looks like a wrong local read. If the source says a name is
local but the original uses `LOAD_DEREF`, the variable is captured from an
outer scope; adding `nonlocal` or moving the binding can fix the cell layout.

## Classes

| Symptom | Likely source |
| --- | --- |
| `LOAD_BUILD_CLASS` body differs | class body statements or base order |
| `CALL` with keywords | metaclass or class keywords |
| `STORE_NAME` in class body | class attribute vs local variable |
| `MAKE_FUNCTION` decorator sequence | decorator order |
| `LOAD_ATTR` `__class__` / `super` | zero-argument `super()` shape |
| `property`/`staticmethod`/`classmethod` calls | missing or misplaced decorator |
| `__slots__` tuple differs | slots declaration |

Remember that the class body executes in its own namespace; a name assigned
there is a class attribute, not a function local.

## Exceptions

| Symptom | Likely source |
| --- | --- |
| Exception-table range differs | `try` body boundaries |
| Handler starts at wrong instruction | `except` clause order/type |
| `CHECK_EXC_MATCH` operand differs | exception class or tuple |
| Bare `except` vs `except BaseException` | handler form |
| `RERAISE` vs `RETURN_VALUE` | re-raise vs return in handler |
| Cleanup code duplicated/moved | `finally` vs context manager |
| `WITH_EXCEPT_START` / `BEFORE_WITH` | `with` statement shape |
| `except*` opcodes/regions | exception-group handler on 3.11+ |

In 3.11+ the exception table is not encoded as `SETUP_*` instructions. Use the
disassembler’s exception regions and the handler targets. Do not infer the
handler layout only from indentation.

## Comprehensions, generators, and lambdas

| Symptom | Likely source |
| --- | --- |
| Extra nested code object | comprehension/generator/lambda |
| `MAKE_FUNCTION` inside loop | lambda or nested `def` |
| `FOR_ITER` inside a separate code object | comprehension |
| `YIELD_VALUE` in a nested code object | generator expression |
| `LIST_APPEND` / `SET_ADD` / `MAP_ADD` | list/set/dict comprehension |
| `LOAD_FAST` of loop variable in outer scope | comprehension scope difference |

A comprehension is a separate code object with its own scope. Python 3.12+
changed comprehension inlining/bytecode in some cases; trust the target
version’s disassembly.

## Pattern matching (3.10+)

- `MATCH_CLASS`, `MATCH_MAPPING`, `MATCH_SEQUENCE`, `MATCH_KEYS` reveal the
  pattern kind.
- `COPY`/`POP_TOP`/`UNPACK_SEQUENCE` reveal capture and unpacking.
- Guard expressions compile as a separate condition before the body.
- Case order matters: the first matching case wins.
- `match` on a value is not the same as `if value == ...`; the class/mapping/
  sequence checks differ.

## Modules, imports, and constants

- `IMPORT_NAME`/`IMPORT_FROM` distinguish `import x` from `from x import y`.
- `STORE_NAME` at module level vs `STORE_FAST` inside a function.
- `LOAD_CONST` values include docstrings; a missing docstring changes the
  module/class/function constant.
- Constant folding may make `1 + 2` and `3` equivalent in optimized bytecode,
  but not always; match the original constant.
- Mutable defaults are created at definition time; don’t “fix” them into
  `None` unless the bytecode says so.
- `__all__`, annotations, and `if __name__ == "__main__":` blocks often show up
  as module-level failures with no obvious line in a function.

## Async and generators

- `GET_AWAITABLE`, `SEND`, `YIELD_VALUE`, `END_SEND`, `END_ASYNC_FOR` indicate
  async shape.
- `async for`/`async with` have distinct cleanup opcodes.
- A generator function has `CO_GENERATOR`; an async generator has
  `CO_ASYNC_GENERATOR`. Returning a generator expression is not the same as a
  generator function.
- `asyncio.gather`/`TaskGroup` are library calls; fix the call shape, not the
  runtime.

## When the whole function is wrong

If a function body is too corrupted to patch locally:

1. reconstruct the function from the original bytecode using the disassembly;
2. preserve the signature and decorators;
3. patch only that function, not the whole file;
4. verify; use `regressed` to detect collateral damage.

Do not rewrite the module to match a guessed architecture. The exact verifier
will reject unrelated changes.

## Regression rule

If `regressed` is non-empty:

- if `progress.delta >= 0` and the regression is local, fix it next;
- otherwise `revert` to the parent revision and choose a smaller hypothesis.

A patch that fixes one object but breaks two is not progress.
