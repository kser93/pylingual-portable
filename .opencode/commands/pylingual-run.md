---
description: Sequentially process .pyc files or a directory with one worker per file
agent: pylingual
---

Process the requested paths: $ARGUMENTS

The argument may be one `.pyc`, several `.pyc` files, or a directory. Build the
ordered file list once. For each file, start exactly one `pylingual-worker`,
wait for it to finish, verify its session report, then move to the next file.
Never run two workers at once. A file is complete only when its report is
`status: "perfect"` and `pylingual_finalize` succeeded. On a technical failure,
start a fresh worker on the same file; do not skip it.

Keep the journal under `workspace/runs/current/journal.jsonl`. Final answer:
total files, perfect count, finalized paths (including `_decompiled_{i}` names),
technical failures/retries, and whether every requested file is perfect.
