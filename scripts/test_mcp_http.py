from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from mcp import Client


ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / "runtime" / "python-3.15.1" / "python.exe"
PORT = 7331


def wait_for_port(timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
                return
        except OSError:
            time.sleep(0.25)
    raise TimeoutError(f"MCP HTTP server did not listen on {PORT}")


async def main() -> int:
    env = {
        **os.environ,
        "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": f"{ROOT / 'src'};{ROOT / 'vendor' / 'pylingual'}",
        "PYLINGUAL_HOME": str(ROOT),
        "HF_HOME": str(ROOT / "models" / "hf-cache"),
        "HF_HUB_CACHE": str(ROOT / "models" / "hf-cache" / "hub"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "TMP": str(ROOT / "workspace" / "tmp"),
        "TEMP": str(ROOT / "workspace" / "tmp"),
    }
    log = (ROOT / "downloads" / "mcp-http-server.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            str(PYTHON),
            "-m",
            "pylingual_portable.mcp_server",
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_port()
        async with Client(f"http://127.0.0.1:{PORT}/mcp") as client:
            tools = await client.list_tools()
            print("tools:", [tool.name for tool in tools.tools])
            caps = await client.call_tool("get_capabilities", {})
            print("capabilities:", json.dumps(caps.structured_content, ensure_ascii=False)[:600])
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
