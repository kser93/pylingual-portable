# OpenCode evaluation harness

The harness measures the **agent + MCP tool** combination, not the decompiler in
isolation. The final score is read from the session on disk, never from the
agent’s prose.

PyLingual is the only allowed decompiler. A run that installs, downloads,
invokes, compares with, or checks the availability of `uncompyle6`,
`decompyle3`, `pycdc`, or any other bytecode-to-source tool is invalid and must
not be counted as a baseline. The harness prompt and `pylingual` agent policy
forbid this explicitly; the agent has no shell permission.

## Prerequisites

```powershell
.\scripts\python.cmd .\scripts\build_harness_fixtures.py --version 3.12
.\scripts\python.cmd .\scripts\opencode_harness.py --check
```

If `opencode` is not on `PATH`, pass `--opencode "C:\path\to\opencode.exe"` or
a `.cmd` wrapper.

## Run

```powershell
# one task, no OpenCode needed: validates task discovery and scoring
.\scripts\python.cmd .\scripts\opencode_harness.py `
  --opencode .\harness\fake_opencode.cmd --only arithmetic --require-all

# real OpenCode agent, all tasks
.\scripts\python.cmd .\scripts\opencode_harness.py `
  --model anthropic/claude-sonnet-5-5 `
  --agent pylingual `
  --require-all
```

`--standalone` is passed to `opencode run`, so the harness uses a private
server and does not interfere with an interactive session. The agent is
`pylingual`; the MCP server comes from `.opencode/opencode.jsonc`.

## Output

```
harness/results/<UTC timestamp>/
  summary.json
  summary.md
  <task>/
    final.py
    report.json
    session.json
    result.json
    opencode.stdout.jsonl
    opencode.stderr.txt
```

`result.json` contains:

- independent final `status` and `summary`;
- initial vs final scores;
- revisions and patches;
- duration, exit code, timeout;
- tool calls observed in the OpenCode event stream;
- remaining failing code objects.

## Success criteria

- **success**: final session `status == "perfect"`.
- **partial**: final `summary.score` improves but is below 1.0.
- **infrastructure error**: no session, OpenCode failure, or unreadable session.

A perfect initial decompilation is a success with zero patches; the harness
still measures it. A task that needs repairs measures the loop.

## Interpreting results

- High success, low revisions: the agent is using diagnostics efficiently.
- High success, high revisions: the prompt or repair skill needs stronger
  triage; inspect raw tool events for repeated full-report reads.
- Low success, high `syntax_error` rate: target-version syntax constraints or
  source reconstruction quality.
- Low success, regressions: patches are too broad; enforce one-code-object
  patches.
- No sessions: MCP startup failure or wrong `cwd`/command.

## Reproducibility

- The fixture `.pyc` files are deterministic build inputs.
- Use the same model, agent, and task manifest for comparisons.
- Run `--repeat 3` for a small distribution; report mean success and score.
- Do not compare runs made with different model snapshots or provider variants.
- The fake OpenCode wrapper only tests harness plumbing; it is not a model
  baseline.
