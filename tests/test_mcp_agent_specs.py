from __future__ import annotations

import asyncio
import json
import unittest

from mcp import Client

from pylingual_portable.mcp_server import mcp


class AgentSpecsTest(unittest.TestCase):
    def run_async(self, coro):
        return asyncio.run(coro)

    def test_agent_tools_are_registered(self) -> None:
        async def scenario() -> None:
            async with Client(mcp) as client:
                tools = await client.list_tools()
                names = {tool.name for tool in tools.tools}
                self.assertIn("get_agent_manifest", names)
                self.assertIn("get_agent_spec", names)
                self.assertIn("get_skill", names)

        self.run_async(scenario())

    def test_manifest_resource_contains_repair_loop(self) -> None:
        async def scenario() -> None:
            async with Client(mcp) as client:
                result = await client.read_resource("pylingual://manifest")
                manifest = json.loads(result.contents[0].text)
                self.assertEqual(manifest["schema"], "pylingual/agent-manifest/v1")
                self.assertIn("server", manifest)
                self.assertEqual(manifest["success"], 'status == "perfect"')
                steps = "\n".join(manifest["loop"])
                self.assertIn("apply_patch", steps)
                self.assertIn("finalize", steps)

        self.run_async(scenario())

    def test_agent_spec_tool_returns_worker_contract(self) -> None:
        async def scenario() -> None:
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_agent_spec",
                    {"role": "worker"},
                )
                payload = result.structured_content
                self.assertEqual(payload["role"], "worker")
                self.assertIn('status: "perfect"', payload["content"])
                self.assertIn("apply_patch", payload["content"])
                self.assertIn("finalize", payload["content"])

        self.run_async(scenario())

    def test_skill_tool_returns_repair_cycle(self) -> None:
        async def scenario() -> None:
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_skill",
                    {"name": "pylingual-repair"},
                )
                payload = result.structured_content
                self.assertEqual(payload["name"], "pylingual-repair")
                self.assertIn("decompile", payload["content"])
                self.assertIn("apply_patch", payload["content"])
                self.assertIn("perfect", payload["content"])

        self.run_async(scenario())

    def test_worker_prompt_includes_path_version_and_contract(self) -> None:
        async def scenario() -> None:
            async with Client(mcp) as client:
                prompts = await client.list_prompts()
                names = {prompt.name for prompt in prompts.prompts}
                self.assertIn("pylingual_worker_task", names)

                result = await client.get_prompt(
                    "pylingual_worker_task",
                    {"path": r"D:\samples\example.pyc", "version": "3.12"},
                )
                text = "\n".join(message.content.text for message in result.messages)
                self.assertIn(r"D:\samples\example.pyc", text)
                self.assertIn("3.12", text)
                self.assertIn('status: "perfect"', text)

        self.run_async(scenario())


if __name__ == "__main__":
    unittest.main()
