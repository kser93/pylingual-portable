---
description: Show the exact status of a PyLingual session
agent: pylingual
---

Show the exact status for the session or `.pyc` target: $ARGUMENTS

If it is a `.pyc` path, start exactly one `pylingual-worker` for that file and
use the session it returns. Otherwise treat it as a session ID. Call
`pylingual_get_session` and `pylingual_get_report` with `detail: "compact"`.

Report the current revision, status, perfect/total count, fixed/remaining
code-object IDs, and any syntax or semantic diagnostics. Do not patch.
