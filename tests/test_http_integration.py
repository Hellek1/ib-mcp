# ruff: noqa: S101
#!/usr/bin/env python3
"""Integration tests for HTTP transport."""

import socket
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_http_server_smoke() -> None:
    """Test that HTTP server starts up and is reachable."""

    # Find a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]

    # Start the server in the background
    server_process = subprocess.Popen(  # noqa: S603
        [
            sys.executable, "-m", "ib_mcp.server",
            "--transport", "http",
            "--http-host", "127.0.0.1",
            "--http-port", str(port)
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=ROOT,
    )

    try:
        # Give the server a moment to start up
        time.sleep(3)

        # Check if server is running
        assert server_process.poll() is None, "Server process exited unexpectedly"

        # Just test that the server is listening on the port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex(('127.0.0.1', port))
            assert result == 0, f"Server not listening on port {port}"

        # Try a simple GET request to see if server responds
        response = requests.get(f"http://127.0.0.1:{port}/", timeout=5.0)

        # Should get some kind of HTTP response (doesn't matter what)
        assert response.status_code is not None, "No HTTP response received"

        print(f"✅ HTTP server test passed - server is listening and responding on port {port}")

    finally:
        # Clean up server process
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
            server_process.wait()


if __name__ == "__main__":
    test_http_server_smoke()
