from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters


ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / "runtime" / "python-3.15.1" / "python.exe"


async def main() -> int:
    env = {
        **os.environ,
        "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": f"{ROOT / 'src'};{ROOT / 'vendor' / 'pylingual'}",
        "PYLINGUAL_HOME": str(ROOT),
        "HF_HOME": str(ROOT / "models" / "hf-cache"),
        "HF_HUB_CACHE": str(ROOT / "models" / "hf-cache" / "hub"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "TMP": str(ROOT / "workspace" / "tmp"),
        "TEMP": str(ROOT / "workspace" / "tmp"),
    }
    params = StdioServerParameters(
        command=str(PYTHON),
        args=["-m", "pylingual_portable.mcp_server", "--transport", "stdio"],
        cwd=str(ROOT),
        env=env,
    )
    async with Client(params) as client:
        tools = await client.list_tools()
        print("tools:", [tool.name for tool in tools.tools])
        caps = await client.call_tool("get_capabilities", {})
        print("capabilities:", json.dumps(caps.structured_content, ensure_ascii=False)[:600])
        doctor = await client.call_tool("doctor", {})
        print("doctor ok:", doctor.structured_content.get("ok"))
        from pylingual_portable import sessions

        existing = sorted(sessions.SESSIONS.glob("ses_*"))
        if existing:
            session_id = existing[-1].name
            report = await client.call_tool(
                "get_report",
                {"session_id": session_id, "detail": "compact"},
            )
            payload = report.structured_content or {}
            print("compact report:", session_id, payload.get("status"), len(payload.get("code_objects", [])))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
