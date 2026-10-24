from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from check_opencode_harness import strip_jsonc


ROOT = Path(__file__).resolve().parent.parent


async def main() -> int:
    config = json.loads(strip_jsonc((ROOT / ".opencode" / "opencode.jsonc").read_text(encoding="utf-8")))
    server = config["mcp"]["servers"]["pylingual"]
    command = server["command"]
    cwd = (ROOT / server.get("cwd", ".")).resolve()
    params = StdioServerParameters(
        command=command[0],
        args=command[1:],
        cwd=str(cwd),
        env={**os.environ},
    )
    async with Client(params) as client:
        tools = await client.list_tools()
        names = [tool.name for tool in tools.tools]
        print("tools:", names)
        if "decompile" not in names or "apply_patch" not in names:
            print("missing required tools")
            return 1
        caps = await client.call_tool("get_capabilities", {})
        payload = caps.structured_content or {}
        print("models:", len(payload.get("models", [])), "cuda:", payload.get("cuda_available"))
        if len(payload.get("models", [])) != 10:
            print("expected 10 model packs")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
