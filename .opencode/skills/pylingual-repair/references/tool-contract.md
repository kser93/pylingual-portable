# PyLingual MCP tool contract

The server name is `pylingual`, so OpenCode exposes direct tools as
`pylingual_<tool>` (Code Mode is disabled for this server).

## Session model

A session is created by `decompile` and persists under
`workspace/sessions/<session_id>/`.

- Revision `0` is the initial decompilation.
- Every accepted `apply_patch` creates a new revision `current + 1`.
- A rejected patch still creates a revision when `dry_run` is false; its report
  explains why it is not perfect. This preserves the audit trail.
- `revert` does not delete history. It creates a new revision whose source is
  copied from the target revision and re-verified.
- `base_revision` is mandatory for `apply_patch`; a mismatch returns
  `error: "base_revision_mismatch"` with `expected`.

## Tools

### `pylingual_decompile`

Input:

```json
{
  "path": "workspace/samples/simple.pyc",
  "version": "3.12",
  "top_k": 10,
  "timeout": 900,
  "device": "auto"
}
```

`top_k` is the upstream-compatible segmentation search budget: the decompiler
tries up to that many alternative statement-boundary segmentations when a code
object fails. The default is `10`, matching upstream PyLingual.


Important output fields:

- `session_id`
- `status`: `perfect`, `semantic_error`, `syntax_error`, or `failed`
- `summary`: `total`, `perfect`, `syntax_errors`, `semantic_errors`, `score`
- `input`: path, SHA-256, size, version
- `current_revision`
- `diagnostics` and `next_actions` (truncated lists)

The initial report is stored at revision 0. Do not call `decompile` again to
continue an existing session.

### `pylingual_get_session`

Returns the session metadata, current revision, status, summary, and revision
history. Use it after `base_revision_mismatch` or when resuming an old session.

### `pylingual_get_report`

Input: `session_id`, optional `revision`, optional `detail`.

- `detail: "summary"` — status and counts, diagnostics, next actions; no full
  code-object table.
- `detail: "compact"` — summary plus failing code objects only; recommended.
- `detail: "full"` — all code objects and diagnostics.

The report contains:

- `status`
- `summary.score` (perfect / total)
- `code_objects[]`: `id`, `name`, `status`, `message`, `line`, `offset`,
  `first_line`
- `diagnostics[]`: `kind` (`syntax_error` or `semantic_error`), message,
  code-object ID, line, offset
- `next_actions[]`: priority, code-object ID, reason
- `source_sha256`, `candidate_sha256`, `original_sha256`

### `pylingual_get_source`

Returns the complete source for a revision and its SHA-256. The source is what
you must send back to `apply_patch`; it is not a diff.

### `pylingual_list_code_objects`

Returns the code-object table for a revision. Use `status` filtering in the
agent, not repeated full reports, when you only need unresolved objects.

### `pylingual_get_code_object`

Input: `session_id`, `code_object_id`, optional `revision`.

Returns:

- the code-object report entry;
- `source_slice` around the failed or first line;
- original `bytecode[]` with offset, opname, arg, argval, starts_line.

Use this instead of guessing from a large source file.

### `pylingual_verify_source`

Input: `session_id`, complete `source`.

Runs the same exact verification as `apply_patch` but does not create a
revision. It is useful for a deliberate dry run; `apply_patch` is the normal
path. Output has `revision: "candidate"` and the full verification report.

### `pylingual_apply_patch`

Input:

```json
{
  "session_id": "ses_...",
  "base_revision": 0,
  "source": "... complete file ...",
  "description": "fix add(): restore subtraction branch",
  "dry_run": false
}
```

Output (on success):

- `revision` (new revision number)
- `status`, `summary`, `diagnostics`, `next_actions`
- `parent_revision`
- `fixed[]`: objects that became perfect
- `regressed[]`: objects that were perfect and are no longer
- `remaining[]`: unresolved objects
- `progress`: `parent_perfect`, `current_perfect`, `delta`

By default the response uses `detail: "compact"` and includes only failing
objects in `code_objects`. Pass `detail: "full"` if you need every code object,
or `detail: "summary"` to omit the table.

If `base_revision` does not match, the result has `error` and no new revision.
If the source does not compile, the result has `status: "syntax_error"` and a
diagnostic. The revision is still recorded unless `dry_run` is true.

### `pylingual_revert`

Input: `session_id`, `target_revision`.

Creates a new revision from the target source and verifies it. Use it when a
patch regressed more than it fixed.

### `pylingual_export`

Input: `session_id`, optional `revision`.

Writes `workspace/exports/<session_id>_r<revision>.py` and returns the relative
path and SHA-256. This is an audit copy, not the final target-file operation.

### `pylingual_finalize`

Input: `session_id`, optional `target_path`.

Writes the source beside the original `.pyc` only when the current revision is
`perfect`. It is single-file and rejects targets outside the original `.pyc`'s
directory. It never overwrites an existing source: if `function.py` already
exists, the result is `function_decompiled_1.py`, then `_2`, and so on. The
response reports both `requested_path` and the actual `path`, plus `renamed`.

### `pylingual_get_capabilities` / `pylingual_doctor`

Return installed versions, toolchains, model packs, CUDA availability, device,
and limits. Use these only for diagnostics; they are not part of the repair
loop.

### `pylingual_cancel`

This build runs decompilation synchronously; cancellation is not supported.
Do not wait on a job ID.

## Status meanings

| Status | Meaning |
| --- | --- |
| `perfect` | Every compared code object is bytecode-equivalent. |
| `semantic_error` | The source compiles, but at least one code object differs. |
| `syntax_error` | The target compiler rejected the candidate source. |
| `failed` | Decompilation or verification itself failed; inspect `error`. |
| `running` | Session created but initial decompilation has not finished. |

`summary.score` is a progress signal, not success. Success is exactly
`status == "perfect"`.
