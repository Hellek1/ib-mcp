# ruff: noqa: S101
#!/usr/bin/env python3
"""Basic tests for the IB MCP Server package."""


import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from ib_async.util import UNSET_DOUBLE

from ib_mcp.server import (  # type: ignore
    IBMCPServer,
    _filter_open_trades,
    _format_open_orders_markdown,
    _format_order_price,
    _format_positions_markdown,
)

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


def test_open_orders_render_stock_option_and_market_orders() -> None:
    """Open orders render one row each; option orders show contract fields, a
    market order's unset prices render blank (not 1.79e308), a stock's default
    0.0 strike renders blank, and a combo credit's negative limit is kept."""

    trades = [
        SimpleNamespace(  # stock limit order (real Contract defaults: strike 0.0)
            order=SimpleNamespace(
                account="U3430526",
                permId=100000101,
                action="BUY",
                totalQuantity=100.0,
                orderType="LMT",
                lmtPrice=185.50,
                auxPrice=0.0,
                tif="DAY",
            ),
            contract=SimpleNamespace(
                symbol="AAPL", secType="STK", strike=0.0, right="", multiplier=""
            ),
            orderStatus=SimpleNamespace(
                status="Submitted", filled=0.0, remaining=100.0
            ),
        ),
        SimpleNamespace(  # option limit order
            order=SimpleNamespace(
                account="U3430526",
                permId=100000102,
                action="BUY",
                totalQuantity=1.0,
                orderType="LMT",
                lmtPrice=2.10,
                auxPrice=0.0,
                tif="GTC",
            ),
            contract=SimpleNamespace(
                symbol="XSP",
                secType="OPT",
                lastTradeDateOrContractMonth="20261218",
                strike=450.0,
                right="P",
                multiplier="100",
            ),
            orderStatus=SimpleNamespace(
                status="PreSubmitted", filled=0.0, remaining=1.0
            ),
        ),
        SimpleNamespace(  # stock market order (unset limit + aux)
            order=SimpleNamespace(
                account="U3430526",
                permId=100000103,
                action="SELL",
                totalQuantity=50.0,
                orderType="MKT",
                lmtPrice=UNSET_DOUBLE,
                auxPrice=0.0,
                tif="DAY",
            ),
            contract=SimpleNamespace(
                symbol="MSFT", secType="STK", strike=0.0, right="", multiplier=""
            ),
            orderStatus=SimpleNamespace(
                status="PreSubmitted", filled=0.0, remaining=50.0
            ),
        ),
        SimpleNamespace(  # combo order sold for a net credit (negative limit)
            order=SimpleNamespace(
                account="U3430526",
                permId=100000104,
                action="SELL",
                totalQuantity=2.0,
                orderType="LMT",
                lmtPrice=-1.50,
                auxPrice=0.0,
                tif="GTC",
            ),
            contract=SimpleNamespace(symbol="XSP", secType="BAG"),
            orderStatus=SimpleNamespace(
                status="PreSubmitted", filled=0.0, remaining=2.0
            ),
        ),
    ]

    result = _format_open_orders_markdown(trades)

    assert "# Open Orders (all accounts)" in result
    for header in ("Perm ID", "Type", "Limit", "Status", "Remaining"):
        assert header in result
    # Stock row: the 0.0 strike + empty option columns all render blank.
    assert "| AAPL | STK |  |  |  |  | LMT |" in result and "185.50" in result
    # Option row surfaces its contract fields; its 0.0 aux renders blank.
    assert "| XSP | OPT | 20261218 | 450.0 | P | 100 | LMT |" in result
    assert "| LMT | 2.10 |  | GTC |" in result
    assert "PreSubmitted" in result and "GTC" in result
    # Market order + unset prices render blank, never the giant sentinel.
    assert "MKT" in result and "e+308" not in result and "1.797" not in result
    # Combo net-credit limit keeps its negative sign (not blanked).
    assert "-1.50" in result


def test_format_order_price_preserves_sign_and_blanks_unused() -> None:
    """Order prices keep their sign (a combo net credit is negative), but an
    unused limit/stop — 0 or the UNSET sentinel on a retrieved order — blanks."""
    assert _format_order_price(185.5) == "185.50"
    assert _format_order_price(-1.50) == "-1.50"  # combo net credit preserved
    assert _format_order_price(0.0) == ""  # unused limit/stop on a retrieved order
    assert _format_order_price(UNSET_DOUBLE) == ""
    assert _format_order_price(float("inf")) == ""
    assert _format_order_price(None) == ""


def test_filter_open_trades_drops_done_and_filters_account() -> None:
    """Terminal (Filled/Cancelled/Inactive) trades are dropped; account narrows."""

    def trade(status: str, acct: str) -> SimpleNamespace:
        return SimpleNamespace(
            order=SimpleNamespace(account=acct),
            orderStatus=SimpleNamespace(status=status),
        )

    trades = [
        trade("Submitted", "U1"),
        trade("PreSubmitted", "U2"),
        trade("Filled", "U1"),
        trade("Cancelled", "U1"),
        trade("Inactive", "U2"),
    ]

    kept = _filter_open_trades(trades)
    assert {t.orderStatus.status for t in kept} == {"Submitted", "PreSubmitted"}

    only_u1 = _filter_open_trades(trades, account="U1")
    assert len(only_u1) == 1 and only_u1[0].order.account == "U1"
