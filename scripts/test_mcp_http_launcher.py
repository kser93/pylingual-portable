from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import time
from pathlib import Path

from mcp import Client


ROOT = Path(__file__).resolve().parent.parent
PORT = 7332


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
    log = (ROOT / "downloads" / "mcp-http-launcher.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            "cmd.exe",
            "/c",
            str(ROOT / "pylingual.cmd"),
            "mcp",
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=str(ROOT),
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_port()
        async with Client(f"http://127.0.0.1:{PORT}/mcp") as client:
            caps = await client.call_tool("get_capabilities", {})
            print("models:", caps.structured_content["models"])
            print("cuda:", caps.structured_content["cuda_available"])
        return 0
    finally:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
            )
        else:
            proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
