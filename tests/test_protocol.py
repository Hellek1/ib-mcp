# ruff: noqa: S101
"""MCP protocol-level tests.

These drive the server through a real ``fastmcp.Client`` instead of calling
tool functions directly, so they catch breakage in how tools are exposed over
MCP (registration, schemas, results, errors) when fastmcp or the MCP SDK
changes.

Every test runs against both protocol eras the server must keep serving:

- ``auto``: what a current client negotiates, the sessionless ``2026-07-28``
  protocol (or newer, as MCP evolves).
- ``legacy``: the session-based ``initialize`` handshake (``2025-11-25`` and
  earlier) still spoken by most deployed MCP clients.
"""

from types import SimpleNamespace

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from ib_mcp.server import IBMCPServer

# First sessionless protocol revision; "auto" must negotiate at least this.
MODERN_PROTOCOL = "2026-07-28"

EXPECTED_TOOLS = {
    "get_account_summary",
    "get_article",
    "get_contract_details",
    "get_fundamental_data",
    "get_historical_data",
    "get_historical_news",
    "get_index_quote",
    "get_option_chain",
    "get_option_quotes",
    "get_positions",
    "lookup_contract",
    "search_contracts",
    "ticker_to_conid",
}

MODES = ["auto", "legacy"]


def assert_protocol_era(mode: str, version: str | None) -> None:
    """Check the negotiated protocol version matches the requested era."""
    assert version, "no protocol version negotiated"
    if mode == "auto":
        assert version >= MODERN_PROTOCOL  # ISO dates compare lexically
    else:
        assert version < MODERN_PROTOCOL


def _offline_server() -> IBMCPServer:
    """Server that looks connected, with IB calls stubbed (no network)."""
    server = IBMCPServer()
    server.connected = True
    position = SimpleNamespace(
        account="DU1234567",
        contract=SimpleNamespace(
            conId=265598,
            symbol="AAPL",
            secType="STK",
            exchange="SMART",
            currency="USD",
            localSymbol="AAPL",
            tradingClass="NMS",
        ),
        position=10.0,
        avgCost=150.25,
    )
    server.ib.positions = lambda account="": [position]  # type: ignore[method-assign,list-item]
    return server


@pytest.mark.parametrize("mode", MODES)
async def test_handshake_and_tool_listing(mode: str) -> None:
    server = IBMCPServer()
    async with Client(server.server, mode=mode) as client:
        assert_protocol_era(mode, client.protocol_version)
        assert client.server_info.name == "IBKR MCP Server"
        assert client.instructions == ("Fetch portfolio and market data using IBKR TWS APIs.")

        tools = await client.list_tools()
        assert {t.name for t in tools} == EXPECTED_TOOLS

        for tool in tools:
            assert tool.description, f"{tool.name} has no description"
            assert tool.input_schema.get("type") == "object", tool.name


@pytest.mark.parametrize("mode", MODES)
async def test_tool_schemas_keep_parameter_metadata(mode: str) -> None:
    """Annotated descriptions, defaults and required args survive to the wire."""
    server = IBMCPServer()
    async with Client(server.server, mode=mode) as client:
        tools = {t.name: t for t in await client.list_tools()}

    hist = tools["get_historical_data"].input_schema
    assert hist["required"] == ["symbol"]
    assert hist["properties"]["symbol"]["description"] == "Stock symbol or conid"
    assert hist["properties"]["duration"]["default"] == "1 M"

    quotes = tools["get_option_quotes"].input_schema
    assert set(quotes["required"]) >= {"symbol", "expiry", "right", "strikes"}
    assert quotes["properties"]["strikes"]["type"] == "array"


@pytest.mark.parametrize("mode", MODES)
async def test_call_tool_returns_markdown(mode: str) -> None:
    server = _offline_server()
    async with Client(server.server, mode=mode) as client:
        result = await client.call_tool("get_positions", {})

    assert not result.is_error
    text = result.content[0].text
    assert text.startswith("# Positions (all accounts)")
    assert "| DU1234567 | AAPL | STK | 10.0 | 150.25 |" in text
    assert result.data == text


@pytest.mark.parametrize("mode", MODES)
async def test_option_quotes_batch_cap_enforced_by_schema(mode: str) -> None:
    """Over MCP the 20-strike cap is advertised in the schema and enforced by
    argument validation before the tool runs (no IB connection needed)."""
    server = IBMCPServer()  # not connected: must not need IB
    async with Client(server.server, mode=mode) as client:
        tools = {t.name: t for t in await client.list_tools()}
        strikes_schema = tools["get_option_quotes"].input_schema["properties"]["strikes"]
        assert strikes_schema["maxItems"] == 20
        assert strikes_schema["minItems"] == 1

        with pytest.raises(ToolError, match="at most 20"):
            await client.call_tool(
                "get_option_quotes",
                {
                    "symbol": "XSP",
                    "expiry": "20260828",
                    "right": "P",
                    "strikes": [float(400 + i) for i in range(21)],
                },
            )


@pytest.mark.parametrize("mode", MODES)
async def test_invalid_arguments_raise_tool_error(mode: str) -> None:
    server = IBMCPServer()
    async with Client(server.server, mode=mode) as client:
        with pytest.raises(ToolError, match="symbol"):
            await client.call_tool("get_historical_data", {"bogus": 1})
