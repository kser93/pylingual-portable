# PyLingual orchestrator contract

## Purpose

Coordinate decompilation of one or more `.pyc` files. You do not decompile or
patch source yourself; a worker owns one file and one session.

## Rules

- Run exactly one worker at a time.
- Give each worker exactly one absolute `.pyc` path.
- Pass the target Python version only when it is explicitly known. Otherwise
  tell the worker to omit `version` and let the server detect it.
- Wait for the worker to finish before starting the next worker.
- Re-read the final report with `get_report`; do not trust the worker's prose.
- A file is complete only when the final report has `status: "perfect"` and
  `finalize` produced a sibling `.py` file.
- If a worker reports a technical failure, start a fresh worker on the same
  file. Do not skip the file and do not use another decompiler.
- Never run two workers concurrently.
- Do not execute a `.pyc` or decompiled source.

## Success flow

```text
for each .pyc:
    start one worker
    wait
    final_report = get_report(session_id)
    if final_report.status == "perfect":
        verify the finalized path exists
        continue
    else:
        start a fresh worker on the same file
```

If the client does not support subagents, follow the worker contract yourself
for one file at a time.

## Patching knowledge

- The worker reads `pylingual-rules` and `get_patching_skill(<version>)` before
  the first patch.
- Rules for other versions are tested as hypotheses, not filtered out.
- A new rule is admitted only after `status: "perfect"` and a finalized file.
  Use `record_patching_rule` with `dry_run=true`; commit it only after the leak
  scan is clean. Provenance stays in the local journal.
