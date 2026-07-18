# ruff: noqa: S101
#!/usr/bin/env python3
"""Tests for the read-only option tools (chain, quotes, index).

Fixtures use values captured from a live IBKR **delayed** feed for XSP on
2026-07-15: subsets of the real strike ladder and expiration list, the
three routing exchanges XSP lists under (IBUSOPT, CBOE, SMART), the
pre-market all-blank quote snapshot, and IB's -1 "no data" price sentinel
observed on the index feed. No live connection is made in these tests.
"""


import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ib_mcp.server import (  # type: ignore  # noqa: E402
    IBMCPServer,
    _fmt_num,
    _fmt_price,
    _format_index_quote_markdown,
    _format_option_chain_markdown,
    _format_option_quotes_markdown,
    _ticker_ready,
)

# Real XSP reference data (subsets), captured 2026-07-15. Strikes are spaced
# every 5 points in this range; expirations are from the live chain.
_XSP_EXPIRATIONS = ["20260715", "20260821", "20260828", "20261218", "20271217"]
_XSP_STRIKES = [
    440.0,
    445.0,
    450.0,
    455.0,
    460.0,
    465.0,
    470.0,
    475.0,
    480.0,
    485.0,
    490.0,
]


def _chain(
    exchange: str,
    strikes: list[float] | None = None,
    expirations: list[str] | None = None,
    trading_class: str = "XSP",
) -> SimpleNamespace:
    return SimpleNamespace(
        tradingClass=trading_class,
        exchange=exchange,
        multiplier="100",
        expirations=list(_XSP_EXPIRATIONS if expirations is None else expirations),
        strikes=list(_XSP_STRIKES if strikes is None else strikes),
    )


def _ticker(
    strike: float,
    bid: float | None = None,
    ask: float | None = None,
    last: float | None = None,
    close: float | None = None,
    greeks: object | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        contract=SimpleNamespace(strike=strike),
        bid=bid,
        ask=ask,
        last=last,
        close=close,
        modelGreeks=greeks,
    )


def test_option_chain_range_filter_and_pagination() -> None:
    """Filter to [450, 480] -> 7 strikes, paged 3 at a time."""
    chains = [_chain("SMART")]
    page1 = _format_option_chain_markdown(
        "XSP",
        sec_type="IND",
        chains=chains,
        min_strike=450,
        max_strike=480,
        max_strikes=3,
    )
    assert "of 7 in range [450, 480]" in page1
    assert "450, 455, 460" in page1
    assert "pass strike_offset=3" in page1
    assert "465" not in page1  # on a later page, not shown yet

    page2 = _format_option_chain_markdown(
        "XSP",
        sec_type="IND",
        chains=chains,
        min_strike=450,
        max_strike=480,
        max_strikes=3,
        strike_offset=3,
    )
    assert "465, 470, 475" in page2
    assert "pass strike_offset=6" in page2


def test_option_chain_no_next_page_hint_on_final_page() -> None:
    """The last page (offset > 0, window ends at total) offers no next page."""
    chains = [_chain("SMART")]
    out = _format_option_chain_markdown(
        "XSP",
        sec_type="IND",
        chains=chains,
        min_strike=450,
        max_strike=480,
        max_strikes=3,
        strike_offset=6,
    )
    assert "Strikes 7–7 of 7" in out
    assert "next page" not in out


def test_option_chain_offset_past_end_is_reported_honestly() -> None:
    """Paging past the end names the overshoot instead of 'none in range'."""
    chains = [_chain("SMART")]
    out = _format_option_chain_markdown(
        "XSP",
        sec_type="IND",
        chains=chains,
        min_strike=450,
        max_strike=480,
        max_strikes=3,
        strike_offset=7,
    )
    assert "strike_offset=7 is past the last strike" in out
    assert "valid offsets: 0-6" in out
    assert "none in range" not in out


def test_option_chain_single_bound_uses_prose_wording() -> None:
    """Single-sided filters read as prose, not pseudo-math infinities."""
    chains = [_chain("SMART")]
    out = _format_option_chain_markdown(
        "XSP", sec_type="IND", chains=chains, min_strike=470, max_strikes=10
    )
    assert "at or above 470" in out
    assert "inf" not in out


def test_option_chain_sorts_unsorted_strikes() -> None:
    """Strikes render ascending regardless of input order (deterministic paging)."""
    chains = [_chain("SMART", strikes=[470.0, 440.0, 460.0, 450.0])]
    out = _format_option_chain_markdown(
        "XSP", sec_type="IND", chains=chains, max_strikes=10
    )
    assert "440, 450, 460, 470" in out


def test_option_chain_dedups_identical_routing_exchanges() -> None:
    """XSP lists the same class on 3 exchanges; collapse to one section."""
    chains = [_chain("IBUSOPT"), _chain("CBOE"), _chain("SMART")]
    out = _format_option_chain_markdown(
        "XSP", sec_type="IND", chains=chains, max_strikes=50
    )
    assert out.count("## Trading Class") == 1
    assert "exchanges: IBUSOPT, CBOE, SMART" in out


def test_option_chain_multiple_classes_advise_trading_class() -> None:
    """SPX-style multi-class chains skip per-group hints and advise filtering.

    One strike_offset cannot page two different strike lists, so the output
    must not emit contradictory per-group next-page hints.
    """
    chains = [
        _chain("SMART", trading_class="SPX", strikes=[4000.0, 4100.0, 4200.0]),
        _chain(
            "SMART",
            trading_class="SPXW",
            strikes=[4000.0, 4050.0, 4100.0, 4150.0, 4200.0],
        ),
    ]
    out = _format_option_chain_markdown(
        "SPX", sec_type="IND", chains=chains, max_strikes=2
    )
    assert out.count("## Trading Class") == 2
    assert "next page" not in out
    assert "pass trading_class to page one chain reliably" in out
    assert "trading classes: SPX, SPXW" in out


def test_option_quotes_blank_cells_for_no_data() -> None:
    """None (pre-market) and IB -1/0 sentinels render as blank cells, not nan/-1."""
    tickers = [
        _ticker(530.0),  # real pre-market snapshot: all None
        _ticker(490.0, bid=-1.0, ask=-1.0, last=0.0, close=-1.0),  # -1/0 sentinels
    ]
    out = _format_option_quotes_markdown(
        "XSP", expiry="20260828", right="P", tickers=tickers
    )
    assert "| 490 |  |  |  |  |  |  |" in out
    assert "| 530 |  |  |  |  |  |  |" in out
    assert "nan" not in out.lower()
    assert "-1" not in out
    assert "None" not in out


def test_option_quotes_skips_unlisted_strikes() -> None:
    """Strikes not listed for the expiry are reported, not silently dropped."""
    tickers = [_ticker(530.0)]
    out = _format_option_quotes_markdown(
        "XSP",
        expiry="20260828",
        right="P",
        tickers=tickers,
        requested_strikes=[455.0, 530.0, 604.0],
    )
    assert "Not listed for this expiry (skipped): 455, 604" in out


def test_option_quotes_empty_reports_all_missing() -> None:
    """When nothing qualifies, say so and list the requested strikes."""
    out = _format_option_quotes_markdown(
        "XSP",
        expiry="20260828",
        right="P",
        tickers=[],
        requested_strikes=[455.0, 530.0],
    )
    assert "No option quotes found for XSP 20260828 P" in out
    assert "Not listed for this expiry (skipped): 455, 530" in out


async def test_option_quotes_batch_cap_rejects_oversized_request() -> None:
    """>20 strikes is rejected before any connection (offline-safe).

    The runtime counts the raw list, exactly as the schema's max_length does,
    so direct calls and MCP clients are held to the same rule.
    """
    server = IBMCPServer()
    strikes = [float(400 + i) for i in range(21)]
    out = await server.get_option_quotes(
        "XSP", expiry="20260828", right="P", strikes=strikes
    )
    assert "max 20" in out
    assert "21 strikes" in out


async def test_option_quotes_dedupes_duplicate_strikes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicates within the cap are deduped (subscribing one contract twice
    would leak an IB market-data line), so they never reach qualification."""
    server = IBMCPServer()
    captured: list[float] = []

    async def fake_qualify(*contracts: object) -> list[object]:
        captured.extend(getattr(c, "strike", 0.0) for c in contracts)
        return []

    monkeypatch.setattr(server.ib, "qualifyContractsAsync", fake_qualify)
    server.connected = True  # skip connecting; only the dedupe path is exercised

    out = await server.get_option_quotes(
        "XSP", expiry="20260828", right="P", strikes=[450.0, 450.0, 455.0]
    )
    assert captured == [450.0, 455.0]  # 3 raw values -> 2 unique contracts
    assert "No option contracts found" in out


async def test_option_quotes_requires_at_least_one_strike() -> None:
    """An empty strike list is rejected before any connection."""
    server = IBMCPServer()
    out = await server.get_option_quotes(
        "XSP", expiry="20260828", right="P", strikes=[]
    )
    assert "at least one strike" in out


def test_fmt_price_blanks_sentinels_and_missing() -> None:
    """Prices blank on None/NaN and IB's -1/0 'no data' sentinels."""
    assert _fmt_price(8.2) == "8.20"
    assert _fmt_price(None) == ""
    assert _fmt_price(-1.0) == ""  # IB no-data sentinel (seen on the index feed)
    assert _fmt_price(0.0) == ""  # no bid / no data
    assert _fmt_price(float("nan")) == ""


def test_fmt_num_preserves_negative_delta() -> None:
    """Greeks keep their sign: a put delta is legitimately negative."""
    assert _fmt_num(-0.4210, decimals=4) == "-0.4210"
    assert _fmt_num(0.1523, decimals=4) == "0.1523"
    assert _fmt_num(None) == ""
    assert _fmt_num(float("nan")) == ""


def test_ticker_ready_requires_fresh_timestamp() -> None:
    """A reused ticker with an unchanged timestamp is stale, not ready.

    ib_async caches Ticker objects per contract for the connection's
    lifetime; without the freshness check, a repeat call for the same
    contract would return the previous call's values.
    """
    ticker = _ticker(758.0, bid=13.24, ask=13.54, close=14.58, greeks=object())
    ticker.contract.secType = "OPT"
    ticker.timestamp = 1000.0
    assert _ticker_ready(ticker, 1000.0) is False  # unchanged -> stale
    assert _ticker_ready(ticker, 999.0) is True  # fresh batch arrived


def test_ticker_ready_gates_options_on_greeks_and_prices() -> None:
    """Options need a price field and model greeks; indices need last or close."""
    nan = float("nan")
    option = _ticker(758.0, bid=nan, ask=nan, last=nan, close=nan)
    option.contract.secType = "OPT"
    option.timestamp = 2.0
    assert _ticker_ready(option, 1.0) is False  # fresh but no data yet

    option.bid = 13.24
    assert _ticker_ready(option, 1.0) is False  # price but no greeks yet
    option.modelGreeks = object()
    assert _ticker_ready(option, 1.0) is True

    # An index that has not traded reports NaN for last; close alone must be
    # enough or the call would burn its whole settle window for data it has.
    index = SimpleNamespace(
        contract=SimpleNamespace(secType="IND"),
        bid=-1.0,
        ask=nan,
        last=nan,
        close=754.36,
        modelGreeks=None,
        timestamp=2.0,
    )
    assert _ticker_ready(index, 1.0) is True

    index.close = nan  # neither last nor close yet -> keep waiting
    assert _ticker_ready(index, 1.0) is False
    index.last = 0.0  # IB's answered no-trade sentinel counts as done
    assert _ticker_ready(index, 1.0) is True
    index.last = 757.23
    assert _ticker_ready(index, 1.0) is True


def test_index_quote_blanks_sentinel_bid_ask() -> None:
    """Index shows last/close; IB's -1 bid/ask sentinels render blank (captured XSP)."""
    ticker = SimpleNamespace(last=754.43, close=754.36, bid=-1.0, ask=-1.0)
    out = _format_index_quote_markdown("XSP", ticker)
    assert "**Last**: 754.43" in out
    assert "**Close**: 754.36" in out
    assert "-1" not in out
    bid_line = next(line for line in out.splitlines() if "Bid" in line)
    assert bid_line.strip() == "- **Bid**:"


def test_option_quotes_render_real_populated_rows() -> None:
    """Real delayed XSP put quotes (captured 2026-07-15) render with greeks.

    Values are the exact delayed-feed snapshot: strike 700 has a last trade,
    strike 758 does not (blank), and both deltas are negative (puts).
    """
    tickers = [
        _ticker(
            700.0,
            bid=3.03,
            ask=3.24,
            last=3.16,
            close=3.48,
            greeks=SimpleNamespace(impliedVol=0.2024, delta=-0.1155, undPrice=None),
        ),
        _ticker(
            758.0,
            bid=13.24,
            ask=13.54,
            last=float("nan"),
            close=14.58,
            greeks=SimpleNamespace(impliedVol=0.1368, delta=-0.4685, undPrice=None),
        ),
    ]
    out = _format_option_quotes_markdown(
        "XSP", expiry="20260828", right="P", tickers=tickers
    )
    assert "| 700 | 3.03 | 3.24 | 3.16 | 3.48 | 0.2024 | -0.1155 |" in out
    assert "| 758 | 13.24 | 13.54 |  | 14.58 | 0.1368 | -0.4685 |" in out
