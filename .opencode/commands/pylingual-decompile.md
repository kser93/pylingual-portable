---
description: Decompile a single .pyc via one PyLingual worker
agent: pylingual
---

Decompile exactly one target: $ARGUMENTS

This command is for one `.pyc` file. Start exactly one `pylingual-worker`
subagent for that file, wait for it to finish, and verify its session report.
The worker must run until `status: "perfect"` and call `pylingual_finalize`.
Do not start another worker while it is running. If it returns a technical
failure, start a fresh worker on the same file. Do not decompile or patch the
file yourself.

Return the session ID, final status, perfect/total count, finalized path, and
any technical failure details.
