from __future__ import annotations

import asyncio

from mcp import Client

from pylingual_portable.mcp_server import mcp


async def main() -> int:
    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = [tool.name for tool in tools.tools]
        print("tools:", names)
        if "finalize" not in names:
            return 1
        result = await client.call_tool(
            "finalize",
            {
                "session_id": "ses_4e326c9d6e84443d",
            },
        )
        print(result.structured_content)
        return 0 if result.structured_content.get("status") == "perfect" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
