from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from check_opencode_harness import frontmatter, strip_jsonc


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    config_path = ROOT / ".opencode" / "opencode.jsonc"
    schema_path = ROOT / "downloads" / "opencode-config-schema.json"
    if not schema_path.is_file():
        print(f"missing schema: {schema_path}")
        return 2
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for path in (config_path, ROOT / "docs" / "opencode-mcp.jsonc"):
        config = json.loads(strip_jsonc(path.read_text(encoding="utf-8")))
        jsonschema.validate(config, schema)

    for agent_path in sorted((ROOT / ".opencode" / "agents").glob("pylingual*.md")):
        agent = frontmatter(agent_path)
        jsonschema.validate({"agents": {agent_path.stem: agent}}, schema)
    for command_path in sorted((ROOT / ".opencode" / "commands").glob("pylingual-*.md")):
        command = frontmatter(command_path)
        command["template"] = command_path.read_text(encoding="utf-8").split("---", 2)[2].strip()
        jsonschema.validate({"commands": {command_path.stem: command}}, schema)
    print("OK: config, agents, and command frontmatter match the OpenCode schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
