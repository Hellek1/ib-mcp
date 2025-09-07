# ruff: noqa: S101
#!/usr/bin/env python3
"""Basic tests for the IB MCP Server package."""


import asyncio
import sys
from pathlib import Path

from ib_mcp.server import IBMCPServer  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def test_server_creation() -> None:
    """Ensure the server initializes and registers handlers."""
    server = IBMCPServer()

    # Basic attributes
    assert hasattr(server, "server")
    assert hasattr(server, "ib")
    assert hasattr(server, "_register_handlers")

    # Handlers should be registered without connecting
    # We won't call network methods in unit tests.
    await asyncio.sleep(0)  # exercise event loop path lightly


def test_server_run_parameters() -> None:
    """Test that the run method accepts the expected parameters."""
    server = IBMCPServer()

    # Test that run method has the expected signature
    import inspect

    sig = inspect.signature(server.run)

    # Check parameter names and defaults
    params = sig.parameters
    assert "transport" in params
    assert "http_host" in params
    assert "http_port" in params

    # Check defaults
    assert params["transport"].default == "stdio"
    assert params["http_host"].default == "127.0.0.1"
    assert params["http_port"].default == 8000
