# Changelog

## 0.3.0 - 2026-10-28

### Fixed

- Exact verification now rejects code-object metadata and constant-type
  differences that upstream `compare_pyc` treated as equal (`x = 1` vs
  `x = True`, differing `co_argcount`, and related cases).
- Source files are written with LF, so `source_sha256` matches the bytes of
  finalized and exported files on Windows.
- `doctor`, `install.ps1 -CheckOnly`, and the MCP probe now verify that pinned
  model snapshot directories contain the required non-empty files and that the
  expected toolchains exist, instead of trusting tracked
  `models/installed.json`. File contents are not re-hashed.
- `pylingual decompile` returns a non-zero exit code unless every code object
  verifies perfectly.
- `finalize` re-runs strict verification and checks `source_sha256` against the
  report, so stale or edited reports cannot bypass the current comparator.

### Added

- MCP tools `get_patching_skill` and `record_patching_rule`, plus
  `pylingual-rules` and versioned patching-skill resources.

### Removed

- The OpenCode CLI evaluation harness, fake launcher, task manifests and CLI
  checks. Agents run in the native OpenCode session; no `opencode` executable is
  invoked by the project.
- One-off debug/probe scripts that referenced local sessions or target-specific
  source snippets.

### Known issues

- The OpenCode command layer for `/pylingual-status`, `/pylingual-finalize` and
  `/pylingual-repair` is still being refined. Commands may route an existing
  session through a worker contract that starts with `decompile`; the MCP tools
  (`get_report`, `finalize`, `apply_patch`) are the authoritative interface.
- Only Python 3.11 has a dedicated patching skill. `get_patching_skill` returns
  that ruleset as a hypothesis for other versions; `record_patching_rule` still
  requires a version with a dedicated skill.
- Model/toolchain health checks verify pinned paths and non-empty files, not
  file hashes.
- Streamable HTTP is a single-user, loopback-oriented mode without
  authentication; do not expose it to a network.

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
