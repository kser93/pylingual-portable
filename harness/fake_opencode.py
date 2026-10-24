from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import Client

from pylingual_portable.mcp_server import mcp


async def main() -> int:
    """Test-only stand-in for `opencode run`; creates one real MCP session."""
    target = os.environ.get("PYLINGUAL_HARNESS_TASK")
    version = os.environ.get("PYLINGUAL_HARNESS_VERSION") or None
    if not target:
        print(json.dumps({"type": "error", "message": "PYLINGUAL_HARNESS_TASK is not set"}))
        return 2

    async with Client(mcp) as client:
        result = await client.call_tool(
            "decompile",
            {
                "path": target,
                "version": version,
                "top_k": 1,
                "timeout": 900,
                "device": "auto",
            },
        )
        payload = result.structured_content or {}
        session_id = payload.get("session_id")
        print(
            json.dumps(
                {
                    "type": "text",
                    "text": (
                        f"session_id={session_id} status={payload.get('status')} "
                        f"summary={json.dumps(payload.get('summary', {}))}"
                    ),
                    "session_id": session_id,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
