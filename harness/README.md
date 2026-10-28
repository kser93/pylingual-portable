# PyLingual fixtures

This directory contains small `.pyc` fixtures used for smoke decompilation and
MCP tests. It is **not** an agent evaluation harness and does not invoke the
OpenCode CLI.

## Files

```text
harness/
  fixtures/src/              readable fixture sources
  fixtures/pyc/<version>/    target-version .pyc inputs
```

## Rebuild fixtures

```powershell
.\scripts\python.cmd .\scripts\build_fixtures.py --version 3.12 --force
.\scripts\python.cmd .\scripts\build_fixtures.py --version 3.10 --force
.\scripts\python.cmd .\scripts\build_fixtures.py --version 3.6 --force
```

Fixtures use only standard library features and cover branches, loops, classes,
exceptions, closures/decorators, and comprehensions/generators.

## Smoke check

```powershell
.\pylingual.cmd decompile `
  .\harness\fixtures\pyc\3.12\arithmetic.pyc `
  -o .\workspace\tmp\arithmetic.py `
  --version 3.12
```

The MCP server can be checked independently with `scripts\probe_mcp.py`; no
OpenCode executable is required.
