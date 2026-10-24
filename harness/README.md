# OpenCode harness

This directory contains the evaluation fixtures and task manifest for the
PyLingual OpenCode agents. The actual configuration lives in `.opencode/`:
the `pylingual` primary orchestrator processes one file at a time and starts
exactly one `pylingual-worker` per `.pyc`. There is no tool-level batch API and
no parallel worker execution.

## Files

```
harness/
  tasks.json                 task manifest
  fixtures/src/              readable fixture sources
  fixtures/pyc/<version>/    target-version .pyc inputs
  fake_opencode.py/.cmd      test-only stand-in for `opencode run`
  results/                   generated evaluation reports (not a baseline)
```

## Build fixtures

```powershell
.\scripts\python.cmd .\scripts\build_harness_fixtures.py --version 3.12 --force
.\scripts\python.cmd .\scripts\build_harness_fixtures.py --version 3.10 --force
.\scripts\python.cmd .\scripts\build_harness_fixtures.py --version 3.6 --force
.\scripts\python.cmd .\scripts\check_opencode_harness.py
.\scripts\python.cmd .\scripts\test_opencode_config_mcp.py
```

Fixtures use only standard library features and cover branches, loops, classes,
exceptions, closures/decorators, and comprehensions/generators.

`tasks.json` is the 3.12 smoke set. `tasks-multi-version.json` adds the same six
fixtures compiled for 3.6 and 3.10:

```powershell
.\scripts\python.cmd .\scripts\opencode_harness.py `
  --tasks .\harness\tasks-multi-version.json --dry-run
```

## Validate the harness without OpenCode

The fake launcher creates a real MCP session (and real exact-verification
report) but does not run a model. It is only a plumbing test:

```powershell
.\scripts\python.cmd .\scripts\opencode_harness.py `
  --opencode .\harness\fake_opencode.cmd --only arithmetic --require-all
```

## Run the real agent

```powershell
.\scripts\python.cmd .\scripts\opencode_harness.py `
  --model anthropic/claude-sonnet-5-5 `
  --agent pylingual `
  --require-all
```

Use `--only arithmetic,loops` to select tasks, `--repeat 3` for repeated runs,
and `--dry-run` to print the commands without executing. `--check` verifies
that the OpenCode executable and fixtures are available. `OPENCODE_BIN` and
`OPENCODE_MODEL` provide defaults for `--opencode` and `--model`.

## Add a task

1. Add a source file under `harness/fixtures/src/`.
2. Compile it:
   `.\scripts\python.cmd .\scripts\build_harness_fixtures.py --version 3.12 --force`
3. Add an entry to `tasks.json` with `id`, `pyc`, `version`, `difficulty`, and
   `description`.
4. Run `--dry-run` and then the task.

The harness reads the final session from `workspace/sessions/` and scores only
`status == "perfect"`. An agent statement is not evidence; the exact verifier
is. Before a run, `opencode_harness.py` performs the same policy preflight as
`check_opencode_harness.py` automatically; use `--no-policy-check` only for
development.

**Policy:** PyLingual is the only allowed decompiler. The runner prompt, the
`pylingual` agent, and the skill forbid installing, downloading, invoking,
comparing with, or checking availability of `uncompyle6`, `decompyle3`,
`pycdc`, or any other decompiler. A baseline produced with another decompiler
is invalid. `scripts/check_opencode_harness.py` checks these policy markers and
fails if `uncompyle6`/`decompyle3` is importable or `pycdc`/`pycdas` is on
`PATH`.

## Interpreting a run

The summary table shows initial and final scores, revision count, duration, and
session ID. Per-task directories contain `final.py`, `report.json`,
`session.json`, raw OpenCode NDJSON events, and `result.json`.

A high revision count with a low success rate usually means the agent is
reading too much context or making multi-object patches. See
`.opencode/skills/pylingual-repair/references/evaluation.md`.
