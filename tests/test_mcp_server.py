# ruff: noqa: S101
#!/usr/bin/env python3
"""Basic tests for the IB MCP Server package."""


import asyncio
import sys
from pathlib import Path

from ib_mcp import IBMCPServer  # type: ignore

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
