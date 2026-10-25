from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters


ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "runtime" / "python-3.15.1"


def server_env() -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONHOME": str(RUNTIME),
        "PYTHONPATH": f"{ROOT / 'src'};{ROOT / 'vendor' / 'pylingual'}",
        "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYLINGUAL_HOME": str(ROOT),
        "PYLINGUAL_LOG_LEVEL": "ERROR",
        "HF_HOME": str(ROOT / "models" / "hf-cache"),
        "HF_HUB_CACHE": str(ROOT / "models" / "hf-cache" / "hub"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "TMP": str(ROOT / "workspace" / "tmp"),
        "TEMP": str(ROOT / "workspace" / "tmp"),
    }


async def probe() -> dict:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "pylingual_portable.mcp_server", "--transport", "stdio"],
        cwd=str(ROOT),
        env=server_env(),
    )
    async with Client(params) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()
        tool_names = {tool.name for tool in tools.tools}
        resource_uris = {str(resource.uri) for resource in resources.resources}
        prompt_names = {prompt.name for prompt in prompts.prompts}

        required_tools = {
            "decompile",
            "get_report",
            "get_code_object",
            "get_source",
            "apply_patch",
            "finalize",
            "get_agent_manifest",
            "get_agent_spec",
            "get_skill",
        }
        required_resources = {
            "pylingual://manifest",
            "pylingual://agents/orchestrator",
            "pylingual://agents/worker",
            "pylingual://skills/pylingual-repair",
        }
        required_prompts = {
            "pylingual_worker_task",
            "pylingual_orchestrator_task",
            "pylingual_repair_loop",
        }

        manifest_result = await client.call_tool("get_agent_manifest", {})
        manifest = manifest_result.structured_content or {}
        worker_result = await client.call_tool("get_agent_spec", {"role": "worker"})
        skill_result = await client.call_tool("get_skill", {"name": "pylingual-repair"})
        capabilities = await client.call_tool("get_capabilities", {})

        missing_tools = sorted(required_tools - tool_names)
        missing_resources = sorted(required_resources - resource_uris)
        missing_prompts = sorted(required_prompts - prompt_names)
        problems = []
        if missing_tools:
            problems.append(f"missing tools: {missing_tools}")
        if missing_resources:
            problems.append(f"missing resources: {missing_resources}")
        if missing_prompts:
            problems.append(f"missing prompts: {missing_prompts}")
        if manifest.get("schema") != "pylingual/agent-manifest/v1":
            problems.append(f"unexpected manifest schema: {manifest.get('schema')!r}")
        if manifest.get("success") != 'status == "perfect"':
            problems.append("manifest success condition is not status == 'perfect'")
        loop = "\n".join(manifest.get("loop", []))
        if "apply_patch" not in loop or "finalize" not in loop:
            problems.append("manifest loop does not include apply_patch/finalize")
        if not worker_result.structured_content or "worker" not in worker_result.structured_content.get("role", ""):
            problems.append("worker agent spec is missing")
        if not skill_result.structured_content or "perfect" not in skill_result.structured_content.get("content", ""):
            problems.append("repair skill is missing the perfect loop")

        return {
            "ok": not problems,
            "problems": problems,
            "tools": len(tool_names),
            "resources": len(resource_uris),
            "prompts": len(prompt_names),
            "manifest_schema": manifest.get("schema"),
            "spec_version": manifest.get("spec_version"),
            "models": len(capabilities.structured_content.get("models", [])),
            "toolchains": len(capabilities.structured_content.get("toolchains", [])),
            "loop": manifest.get("loop", []),
        }


def main() -> int:
    try:
        result = asyncio.run(probe())
    except Exception as exc:  # noqa: BLE001 - report the preflight failure
        print(json.dumps({"ok": False, "error": repr(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
