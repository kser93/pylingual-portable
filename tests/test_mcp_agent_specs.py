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

    def test_manifest_lists_registered_tools_and_resources(self) -> None:
        async def scenario() -> None:
            async with Client(mcp) as client:
                tools = {tool.name for tool in (await client.list_tools()).tools}
                resources = {str(resource.uri) for resource in (await client.list_resources()).resources}
                prompts = {prompt.name for prompt in (await client.list_prompts()).prompts}
                result = await client.call_tool("get_agent_manifest", {})
                manifest = result.structured_content

                self.assertLessEqual(set(manifest["tools"]), tools)
                self.assertLessEqual(set(manifest["resources"].values()), resources)
                self.assertLessEqual(set(manifest["prompts"]), prompts)
                self.assertIn("get_patching_skill", tools)
                self.assertIn("record_patching_rule", tools)
                self.assertIn("pylingual://skills/pylingual-rules", resources)
                self.assertIn("pylingual://skills/pylingual-patching-3.11", resources)

        self.run_async(scenario())

    def test_patching_skill_falls_back_for_unversioned_targets(self) -> None:
        async def scenario() -> None:
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_patching_skill",
                    {"version": "3.12", "include_all_versions": True},
                )
                payload = result.structured_content
                self.assertEqual(payload["target"], "3.12")
                self.assertFalse(payload["primary"]["available"])
                self.assertEqual(payload["primary"]["rules"], [])
                self.assertTrue(any(item["version"] == "3.11" for item in payload["others"]))

                target = await client.call_tool(
                    "get_patching_skill",
                    {"version": "3.11", "include_all_versions": False},
                )
                target_payload = target.structured_content
                self.assertTrue(target_payload["primary"]["available"])
                self.assertTrue(target_payload["primary"]["rules"])

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
                    {"path": r"C:\samples\example.pyc", "version": "3.12"},
                )
                text = "\n".join(message.content.text for message in result.messages)
                self.assertIn(r"C:\samples\example.pyc", text)
                self.assertIn("3.12", text)
                self.assertIn('status: "perfect"', text)

        self.run_async(scenario())


if __name__ == "__main__":
    unittest.main()
