from __future__ import annotations

import asyncio
import os
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters


ROOT = Path(__file__).resolve().parent.parent


async def main() -> int:
    params = StdioServerParameters(
        command="cmd.exe",
        args=["/c", "pylingual.cmd", "mcp", "--stdio"],
        cwd=str(ROOT),
        env={**os.environ},
    )
    async with Client(params) as client:
        caps = await client.call_tool("get_capabilities", {})
        print("models:", caps.structured_content["models"])
        doctor = await client.call_tool("doctor", {})
        print("doctor ok:", doctor.structured_content["ok"])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
