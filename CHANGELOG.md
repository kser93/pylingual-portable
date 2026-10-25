# Changelog

## 0.2.0 - 2026-10-25

### Added

- `install.ps1`: bootstrap installer for Windows x64. It clones the repository
  with submodules, installs Python 3.15.1 and runtime dependencies, downloads
  CPython 3.6–3.15 toolchains and the ten model packs, verifies the MCP server
  and prints a project-local OpenCode configuration.
- MCP agent/skill contracts: `pylingual://manifest`,
  `pylingual://agents/orchestrator`, `pylingual://agents/worker`,
  `pylingual://skills/pylingual-repair`, three MCP prompts and the tools
  `get_agent_manifest`, `get_agent_spec`, `get_skill`.
- Project-local OpenCode MCP configuration and installation documentation.
- MCP preflight probe (`scripts/probe_mcp.py`) that starts the stdio server and
  validates tools, resources, prompts and the agent manifest.
- `CHANGELOG.md` and release notes.

### Fixed

- Hash-based `.pyc` files with `timestamp=None` no longer crash the decompiler.
  The source header now reads `unknown (hash-based pyc)`.
- Vendor integrity checking now hashes all tracked files, validates submodule
  heads, gitlinks and dirty trees, and fails closed on `--update`.

### Changed

- PyLingual and xdis are git submodules pinned to upstream commits.
- Documentation was rewritten around installation, usage and agent discovery.
- The MCP server reports version 0.2.0 and exposes 17 tools, 4 resources and
  3 prompts.

### Validation

- 30 public `.pyc` files from the xdis test corpus were decompiled through the
  native orchestrator/worker path: 30/30 `perfect`, 384/384 code objects.
  This was a local run, not a CI baseline.

## 0.1.0 - 2026-10-24

- Initial portable PyLingual build with local runtime, CLI, MCP server,
  sessions, exact verification, patch loop, toolchains and model packs.
