---
description: Export a PyLingual revision and report its verification status
agent: pylingual
---

Export the requested revision for: $ARGUMENTS

Parse the argument as `session_id` plus an optional revision. Call
`pylingual_get_session`, then `pylingual_export` for the requested revision or
the current revision. Also fetch a compact report and report the exact status,
perfect/total count, export path, and remaining failures. Do not patch.
