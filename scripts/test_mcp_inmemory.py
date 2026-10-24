from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp import Client

from pylingual_portable.mcp_server import mcp


async def main() -> int:
    async with Client(mcp) as client:
        tools = await client.list_tools()
        print("tools:", [tool.name for tool in tools.tools])

        caps = await client.call_tool("get_capabilities", {})
        print("capabilities:", json.dumps(caps.structured_content, ensure_ascii=False)[:800])

        result = await client.call_tool(
            "decompile",
            {
                "path": str(Path("workspace/samples/simple.pyc").resolve()),
                "version": "3.12",
                "top_k": 1,
                "timeout": 900,
            },
        )
        payload = result.structured_content
        print("decompile:", json.dumps(payload, ensure_ascii=False)[:1200])
        session_id = payload["session_id"]

        report = await client.call_tool("get_report", {"session_id": session_id})
        print("report status:", report.structured_content["status"], report.structured_content["summary"])

        source_result = await client.call_tool("get_source", {"session_id": session_id})
        source = source_result.structured_content["source"]
        revision = source_result.structured_content["revision"]
        print("source revision:", revision)

        code_objects = await client.call_tool("list_code_objects", {"session_id": session_id})
        first_id = code_objects.structured_content["result"][0]["id"]
        code_object = await client.call_tool(
            "get_code_object",
            {"session_id": session_id, "code_object_id": first_id},
        )
        print("code object:", json.dumps(code_object.structured_content, ensure_ascii=False)[:600])

        bad_source = source.replace("        return a + b", "        return a - b", 1)
        verified = await client.call_tool(
            "verify_source",
            {"session_id": session_id, "source": bad_source},
        )
        print("verify bad source:", verified.structured_content["status"], verified.structured_content["summary"])
        bad = await client.call_tool(
            "apply_patch",
            {
                "session_id": session_id,
                "base_revision": revision,
                "source": bad_source,
                "description": "intentional bad patch",
            },
        )
        print("bad patch:", bad.structured_content["status"], bad.structured_content["summary"])
        bad_revision = bad.structured_content["revision"]

        good = await client.call_tool(
            "apply_patch",
            {
                "session_id": session_id,
                "base_revision": bad_revision,
                "source": source,
                "description": "restore correct source",
            },
        )
        print("good patch:", good.structured_content["status"], good.structured_content["summary"])

        reverted = await client.call_tool(
            "revert",
            {"session_id": session_id, "target_revision": revision},
        )
        print("revert:", reverted.structured_content["status"], reverted.structured_content["revision"])

        exported = await client.call_tool("export", {"session_id": session_id})
        print("export:", exported.structured_content)
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
