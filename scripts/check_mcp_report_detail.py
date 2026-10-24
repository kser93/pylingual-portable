from __future__ import annotations

import asyncio
import json
import sys

from mcp import Client

from pylingual_portable.mcp_server import mcp


async def main() -> int:
    session_id = sys.argv[1]
    async with Client(mcp) as client:
        for detail in ("summary", "compact", "full"):
            result = await client.call_tool(
                "get_report",
                {"session_id": session_id, "detail": detail},
            )
            payload = result.structured_content or {}
            print(
                detail,
                "status=", payload.get("status"),
                "objects=", len(payload.get("code_objects", [])),
                "truncated=", payload.get("truncated"),
            )
        result = await client.call_tool(
            "apply_patch",
            {
                "session_id": session_id,
                "base_revision": 2,
                "source": "def broken(:\n",
                "dry_run": True,
                "description": "syntax error dry run",
            },
        )
        payload = result.structured_content or {}
        print("dry syntax:", payload.get("status"), payload.get("summary"), payload.get("error"))
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
