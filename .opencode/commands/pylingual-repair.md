---
description: Run the exact-verification repair loop for one file via one worker
agent: pylingual
---

Recover exactly one file: $ARGUMENTS

This command is for one `.pyc` or one existing session. Start exactly one
`pylingual-worker` subagent, wait for completion, and verify the returned
session. The worker must continue until `status: "perfect"` and finalize the
source. Do not run workers in parallel and do not patch the source yourself.
If the worker reports a technical failure, start a fresh worker on the same
file; do not skip it and do not use another decompiler.

Return the session ID, final revision, status, perfect/total count, finalized
path, and any remaining technical failure.
