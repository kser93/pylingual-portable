from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
OPENCODE = ROOT / ".opencode"
sys.path.insert(0, str(ROOT / "scripts"))

from check_vendor import check_components  # noqa: E402


def strip_jsonc(text: str) -> str:
    result = []
    index = 0
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < len(text):
            next_char = text[index + 1]
            if next_char == "/":
                index += 2
                while index < len(text) and text[index] not in "\r\n":
                    index += 1
                continue
            if next_char == "*":
                index += 2
                while index + 1 < len(text) and text[index : index + 2] != "*/":
                    index += 1
                index += 2
                continue
        result.append(char)
        index += 1
    return "".join(result)


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: frontmatter is not a mapping")
    return data


def main() -> int:
    errors = []
    vendor = check_components()
    for error in vendor["errors"]:
        errors.append(f"vendor: {error}")
    config_path = OPENCODE / "opencode.jsonc"
    config = json.loads(strip_jsonc(config_path.read_text(encoding="utf-8")))
    server = config.get("mcp", {}).get("servers", {}).get("pylingual", {})
    if server.get("type") != "local":
        errors.append("pylingual MCP server must be local")
    if server.get("codemode") is not False:
        errors.append("pylingual MCP server should use codemode: false")
    if not server.get("command"):
        errors.append("pylingual MCP server has no command")

    def rules(meta: dict) -> list[dict]:
        return [item for item in meta.get("permissions", []) if isinstance(item, dict)]

    def has_rule(meta: dict, action: str, resource: str, effect: str) -> bool:
        return any(
            item.get("action") == action
            and item.get("resource") == resource
            and item.get("effect") == effect
            for item in rules(meta)
        )

    agent = OPENCODE / "agents" / "pylingual.md"
    agent_text = agent.read_text(encoding="utf-8")
    agent_meta = frontmatter(agent)
    if agent_meta.get("mode") != "primary":
        errors.append("pylingual agent must be primary")
    for action in ("shell", "webfetch", "websearch", "execute"):
        if not has_rule(agent_meta, action, "*", "deny"):
            errors.append(f"pylingual orchestrator does not deny {action}")
    if not has_rule(agent_meta, "external_directory", "*", "allow"):
        errors.append("pylingual orchestrator must allow user-supplied external paths")
    if not has_rule(agent_meta, "edit", "*", "deny"):
        errors.append("pylingual orchestrator must deny general edit")
    if not has_rule(agent_meta, "edit", "workspace/runs/**", "allow"):
        errors.append("pylingual orchestrator must allow only its journal edit path")
    if not has_rule(agent_meta, "subagent", "*", "deny"):
        errors.append("pylingual orchestrator must deny general subagents")
    if not has_rule(agent_meta, "subagent", "pylingual-worker", "allow"):
        errors.append("pylingual orchestrator must allow only pylingual-worker")
    policy_markers = ("PyLingual is the only allowed decompiler", "uncompyle6", "decompyle3", "pycdc")
    for marker in policy_markers:
        if marker not in agent_text:
            errors.append(f"pylingual orchestrator policy is missing marker: {marker}")
    if "one worker at a time" not in agent_text:
        errors.append("pylingual orchestrator must enforce one worker at a time")

    worker = OPENCODE / "agents" / "pylingual-worker.md"
    worker_text = worker.read_text(encoding="utf-8")
    worker_meta = frontmatter(worker)
    if worker_meta.get("mode") != "subagent":
        errors.append("pylingual-worker must be a subagent")
    for action in ("shell", "edit", "webfetch", "websearch", "execute", "subagent"):
        if not has_rule(worker_meta, action, "*", "deny"):
            errors.append(f"pylingual-worker does not deny {action}")
    if not has_rule(worker_meta, "pylingual_*", "*", "allow"):
        errors.append("pylingual-worker must allow pylingual tools")
    for marker in policy_markers:
        if marker not in worker_text:
            errors.append(f"pylingual-worker policy is missing marker: {marker}")
    if "one" not in worker_text.lower():
        errors.append("pylingual-worker must declare a one-file contract")

    commands = sorted((OPENCODE / "commands").glob("pylingual-*.md"))
    if len(commands) < 4:
        errors.append(f"expected at least 4 pylingual commands, found {len(commands)}")
    for command in commands:
        meta = frontmatter(command)
        if meta.get("agent") != "pylingual":
            errors.append(f"{command.name}: agent is not pylingual")

    skill = OPENCODE / "skills" / "pylingual-repair" / "SKILL.md"
    skill_text = skill.read_text(encoding="utf-8")
    skill_meta = frontmatter(skill)
    if not skill_meta.get("description"):
        errors.append("pylingual-repair skill has no description")
    for marker in ("PyLingual is the only allowed decompiler", "uncompyle6"):
        if marker not in skill_text:
            errors.append(f"pylingual-repair skill policy is missing marker: {marker}")
    references = sorted((skill.parent / "references").glob("*.md"))
    if len(references) < 4:
        errors.append(f"expected at least 4 skill references, found {len(references)}")

    runner_text = (ROOT / "scripts" / "opencode_harness.py").read_text(encoding="utf-8")
    for marker in ("uncompyle6", "PyLingual is the", "only allowed decompiler"):
        if marker not in runner_text:
            errors.append(f"harness runner policy is missing marker: {marker}")

    task_manifests = [
        ROOT / "harness" / "tasks.json",
        ROOT / "harness" / "tasks-multi-version.json",
    ]
    task_count = 0
    for tasks_path in task_manifests:
        tasks = json.loads(tasks_path.read_text(encoding="utf-8")).get("tasks", [])
        if not tasks:
            errors.append(f"{tasks_path.relative_to(ROOT)} has no tasks")
        task_count += len(tasks)
        for task in tasks:
            target = ROOT / task["pyc"]
            if not target.is_file():
                errors.append(f"missing fixture: {target}")

    for module in ("uncompyle6", "decompyle3"):
        if importlib.util.find_spec(module) is not None:
            errors.append(f"forbidden alternative decompiler is installed: {module}")
    for executable in ("pycdc", "pycdas"):
        if shutil.which(executable):
            errors.append(f"forbidden alternative decompiler is on PATH: {executable}")

    if errors:
        print("FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        f"OK: {len(commands)} commands, {task_count} tasks "
        f"({len(task_manifests)} manifests), {len(references)} references, "
        f"{len(vendor['components'])} vendor components"
    )
    print(f"agent: {agent.relative_to(ROOT)}")
    print(f"mcp: {server.get('command')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
