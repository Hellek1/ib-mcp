# ruff: noqa: S101
"""Integration tests that run the real CLI entry point over each transport.

The server is started as a subprocess (``python -m ib_mcp.server``) and driven
with a real MCP client over stdio and streamable HTTP, in both protocol eras
(see ``test_protocol.py``). No IB connection is needed: listing tools never
connects to TWS.
"""

import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from tests.test_protocol import EXPECTED_TOOLS, MODES, assert_protocol_era

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(proc: subprocess.Popen[bytes], port: int, log: Path, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            tail = log.read_text(errors="replace")[-2000:]
            pytest.fail(f"server exited early ({proc.returncode}): {tail}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    pytest.fail(f"server not listening on port {port} after {timeout}s")


@pytest.fixture(scope="module")
def http_server_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    port = _free_port()
    log = tmp_path_factory.mktemp("http") / "server.log"
    log_file = log.open("wb")
    proc = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "ib_mcp.server",
            "--transport",
            "http",
            "--http-host",
            "127.0.0.1",
            "--http-port",
            str(port),
        ],
        stdout=subprocess.DEVNULL,
        stderr=log_file,
        cwd=ROOT,
    )
    try:
        _wait_for_port(proc, port, log, timeout=30)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log_file.close()


@pytest.mark.parametrize("mode", MODES)
async def test_streamable_http_round_trip(http_server_url: str, mode: str) -> None:
    async with Client(http_server_url, mode=mode, timeout=30) as client:
        assert_protocol_era(mode, client.protocol_version)
        tools = await client.list_tools()
    assert {t.name for t in tools} == EXPECTED_TOOLS


@pytest.mark.parametrize("mode", MODES)
async def test_stdio_round_trip(mode: str) -> None:
    transport = StdioTransport(command=sys.executable, args=["-m", "ib_mcp.server"], cwd=str(ROOT))
    async with Client(transport, mode=mode, timeout=30) as client:
        assert_protocol_era(mode, client.protocol_version)
        tools = await client.list_tools()
    assert {t.name for t in tools} == EXPECTED_TOOLS
