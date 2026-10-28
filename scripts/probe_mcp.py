from __future__ import annotations

import argparse
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


async def probe(*, skip_models: bool = False, skip_toolchains: bool = False) -> dict:
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

        manifest_result = await client.call_tool("get_agent_manifest", {})
        manifest = manifest_result.structured_content or {}
        manifest_resources = manifest.get("resources")
        if not isinstance(manifest_resources, dict):
            manifest_resources = {}
        required_tools = {str(name) for name in (manifest.get("tools") or [])}
        required_resources = {str(uri) for uri in manifest_resources.values()}
        required_prompts = {str(name) for name in (manifest.get("prompts") or [])}

        worker_result = await client.call_tool("get_agent_spec", {"role": "worker"})
        skill_result = await client.call_tool("get_skill", {"name": "pylingual-repair"})
        patching_result = await client.call_tool(
            "get_patching_skill",
            {"version": "3.11", "include_all_versions": False},
        )
        capabilities = await client.call_tool("get_capabilities", {})
        doctor_result = await client.call_tool(
            "doctor",
            {
                "require_models": not skip_models,
                "require_toolchains": not skip_toolchains,
            },
        )

        missing_tools = sorted(required_tools - tool_names)
        missing_resources = sorted(required_resources - resource_uris)
        missing_prompts = sorted(required_prompts - prompt_names)
        unlisted_tools = sorted(tool_names - required_tools)
        unlisted_resources = sorted(resource_uris - required_resources)
        unlisted_prompts = sorted(prompt_names - required_prompts)
        problems = []
        if not required_tools:
            problems.append("manifest does not list tools")
        if not required_resources:
            problems.append("manifest does not list resources")
        if not required_prompts:
            problems.append("manifest does not list prompts")
        if missing_tools:
            problems.append(f"missing tools: {missing_tools}")
        if missing_resources:
            problems.append(f"missing resources: {missing_resources}")
        if missing_prompts:
            problems.append(f"missing prompts: {missing_prompts}")
        if unlisted_tools:
            problems.append(f"tools missing from manifest: {unlisted_tools}")
        if unlisted_resources:
            problems.append(f"resources missing from manifest: {unlisted_resources}")
        if unlisted_prompts:
            problems.append(f"prompts missing from manifest: {unlisted_prompts}")
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
        patching_payload = patching_result.structured_content or {}
        if not patching_payload.get("primary", {}).get("rules"):
            problems.append("3.11 patching skill is missing rules")
        capability_payload = capabilities.structured_content or {}
        model_count = len(capability_payload.get("models", []))
        toolchain_count = len(capability_payload.get("toolchains", []))
        if not skip_models and model_count != 10:
            problems.append(f"expected 10 complete model packs, found {model_count}")
        if not skip_toolchains and toolchain_count != 10:
            problems.append(f"expected 10 toolchains, found {toolchain_count}")
        doctor_payload = doctor_result.structured_content or {}
        if not doctor_payload.get("ok"):
            problems.append("doctor is not healthy")

        return {
            "ok": not problems,
            "problems": problems,
            "tools": len(tool_names),
            "resources": len(resource_uris),
            "prompts": len(prompt_names),
            "manifest_tools": len(required_tools),
            "manifest_resources": len(required_resources),
            "manifest_prompts": len(required_prompts),
            "manifest_schema": manifest.get("schema"),
            "spec_version": manifest.get("spec_version"),
            "models": model_count,
            "toolchains": toolchain_count,
            "doctor_ok": bool(doctor_payload.get("ok")),
            "loop": manifest.get("loop", []),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe the local PyLingual MCP server")
    parser.add_argument("--skip-models", action="store_true")
    parser.add_argument("--skip-toolchains", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(
            probe(skip_models=args.skip_models, skip_toolchains=args.skip_toolchains)
        )
    except Exception as exc:  # noqa: BLE001 - report the preflight failure
        print(json.dumps({"ok": False, "error": repr(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
