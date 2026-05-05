# ruff: noqa: S101
#!/usr/bin/env python3
"""Basic tests for the IB MCP Server package."""


import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from ib_mcp.server import IBMCPServer, _format_positions_markdown  # type: ignore

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


def test_get_positions_includes_option_contract_fields() -> None:
    """Ensure option positions include contract metadata in the markdown table."""

    positions = [
        SimpleNamespace(
            account="U3430526",
            contract=SimpleNamespace(
                conId=14016743,
                symbol="6506",
                secType="STK",
                exchange="TSEJ",
                currency="JPY",
                localSymbol="6506.T",
                tradingClass="6506",
            ),
            position=100.0,
            avgCost=4652.4646,
        ),
        SimpleNamespace(
            account="U3430526",
            contract=SimpleNamespace(
                conId=674453115,
                symbol="SPY",
                secType="OPT",
                lastTradeDateOrContractMonth="20261218",
                strike=600.0,
                right="P",
                multiplier="100",
                currency="USD",
                localSymbol="SPY   261218P00600000",
                tradingClass="SPY",
            ),
            position=1.0,
            avgCost=1819.0488,
        ),
    ]

    result = _format_positions_markdown(positions)

    assert "Expiry" in result
    assert "Strike" in result
    assert "Right" in result
    assert "Multiplier" in result
    assert "SPY   261218P00600000" in result
    assert "20261218" in result
    assert "600.0" in result
    assert "| U3430526 | SPY | OPT | 1.0 | 1819.05 |" in result
