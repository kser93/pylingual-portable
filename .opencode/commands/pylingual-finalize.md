---
description: Write a perfect PyLingual revision beside its original .pyc
agent: pylingual
---

Finalize the requested session: $ARGUMENTS

Parse the argument as `session_id`. Call `pylingual_get_session` and
`pylingual_get_report`. Only if the report status is exactly `perfect`, call
`pylingual_finalize` with the session ID. Existing source files are never
overwritten; `finalize` will choose `_decompiled_{i}` automatically. If the
session is not perfect, do not finalize it; report the remaining failures.
