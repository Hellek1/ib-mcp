"""FastMCP-based MCP server for Interactive Brokers (alternate implementation).

This mirrors the tools and structure from the legacy server, but uses FastMCP
for simpler registration and JSON-schema generation from type hints.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

import defusedxml.ElementTree as ET
import ib_async as ib
from fastmcp import FastMCP
from pydantic import Field

logger = logging.getLogger(__name__)


class IBMCPServer:
    """Interactive Brokers MCP Server (FastMCP edition)."""

    def __init__(
        self, host: str = "127.0.0.1", port: int = 7496, client_id: int = 1
    ) -> None:
        self.server = FastMCP(
            name="IBKR MCP Server",
            instructions="Fetch portfolio and market data using IBKR TWS APIs.",
        )
        self.ib = ib.IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False
        self.news_provider_codes: str = ""

        # Register FastMCP tools
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register tools using FastMCP decorators. Uses closures that capture self."""

        async def _ensure_connected() -> None:
            if self.connected:
                return
            try:
                await self.ib.connectAsync(
                    self.host, self.port, self.client_id, readonly=True
                )
                self.connected = True
                logger.info("Connected to IB at %s:%s", self.host, self.port)
                news_providers = await self.ib.reqNewsProvidersAsync()
                self.news_provider_codes = "+".join(np.code for np in news_providers)
                logger.info("News providers retrieved: %s", self.news_provider_codes)
            except Exception as e:  # pragma: no cover - relies on external service
                logger.error("Failed to connect to IB: %s", e)
                raise ConnectionError(
                    f"Cannot connect to Interactive Brokers: {e}"
                ) from e

        def _create_contract(
            symbol: str,
            sec_type: str = "STK",
            exchange: str = "SMART",
            currency: str = "USD",
        ) -> ib.Contract:
            if symbol.isdigit():
                return ib.Contract(conId=int(symbol))
            if sec_type == "STK":
                return ib.Stock(symbol=symbol, exchange=exchange, currency=currency)
            if sec_type in ("FOREX", "CASH"):
                return ib.Forex(pair=symbol)
            if sec_type == "FUT":
                return ib.Future(symbol=symbol, exchange=exchange)
            if sec_type == "OPT":
                # Option expects strike as float, not currency as 3rd arg
                return ib.Option(symbol=symbol, exchange=exchange, currency=currency)
            return ib.Contract(
                symbol=symbol, secType=sec_type, exchange=exchange, currency=currency
            )

        def _flatten_contracts(contracts: list[Any]) -> list[ib.Contract]:
            # Recursively flatten nested contract lists and filter out None
            result: list[ib.Contract] = []
            for c in contracts:
                if isinstance(c, ib.Contract):
                    result.append(c)
                elif isinstance(c, list):
                    result.extend(_flatten_contracts(c))
            return result

        def _xml_to_markdown(xml_data: str) -> str:
            """Convert XML data to markdown; return as-is if not XML."""
            try:
                if not xml_data or not xml_data.strip().startswith("<"):
                    return xml_data
                root = ET.fromstring(xml_data)
                return _xml_element_to_markdown(root)
            except ET.ParseError:
                return xml_data

        def _format_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
            """Format data as a markdown table."""
            if not headers or not rows:
                return ""

            # Create header row
            header_row = "| " + " | ".join(headers) + " |"

            # Create separator row
            separator_row = "| " + " | ".join("---" for _ in headers) + " |"

            # Create data rows
            data_rows = []
            for row in rows:
                # Pad row to match header length if needed
                padded_row = row + [""] * (len(headers) - len(row))
                data_rows.append("| " + " | ".join(padded_row[: len(headers)]) + " |")

            return "\n".join([header_row, separator_row] + data_rows)

        def _format_markdown_list(items: list[str], ordered: bool = False) -> str:
            """Format items as a markdown list."""
            if not items:
                return ""

            if ordered:
                return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
            else:
                return "\n".join(f"- {item}" for item in items)

        def _xml_element_to_markdown(element: ET.Element, level: int = 0) -> str:
            markdown = ""
            indent = "  " * level
            if level == 0:
                markdown += f"# {element.tag}\n\n"
            elif level == 1:
                markdown += f"## {element.tag}\n\n"
            elif level == 2:
                markdown += f"### {element.tag}\n\n"
            else:
                markdown += f"{indent}**{element.tag}**\n\n"
            if element.text and element.text.strip():
                markdown += f"{indent}{element.text.strip()}\n\n"
            if element.attrib:
                for key, value in element.attrib.items():
                    markdown += f"{indent}- **{key}**: {value}\n"
                markdown += "\n"
            for child in element:
                markdown += _xml_element_to_markdown(child, level + 1)
            return markdown

        @self.server.tool(
            description="Look up contract details by ticker symbol and optional exchange/currency"
        )
        async def lookup_contract(
            symbol: Annotated[str, "Stock symbol (e.g., AAPL, GOOGL, etc.)"],
            sec_type: Annotated[
                str, "Security type (e.g., STK, OPT, FUT, etc.)"
            ] = "STK",
            exchange: Annotated[
                str, "Exchange (e.g., SMART, NYSE, NASDAQ, etc.)"
            ] = "SMART",
            currency: Annotated[str, "Currency (e.g., USD, EUR, etc.)"] = "USD",
        ) -> str:
            await _ensure_connected()
            contract = _create_contract(symbol, sec_type, exchange, currency)
            try:
                contracts_raw = await self.ib.qualifyContractsAsync(contract)
                contracts = _flatten_contracts(contracts_raw)
                if not contracts:
                    return f"No contract found for {symbol}"

                if len(contracts) == 1:
                    c = contracts[0]
                    return "\n".join(
                        [
                            f"# Contract Details for {symbol}",
                            "",
                            f"- **ConID**: {getattr(c, 'conId', '')}",
                            f"- **Symbol**: {getattr(c, 'symbol', '')}",
                            f"- **Security Type**: {getattr(c, 'secType', '')}",
                            f"- **Exchange**: {getattr(c, 'exchange', '')}",
                            f"- **Primary Exchange**: {getattr(c, 'primaryExchange', '')}",
                            f"- **Currency**: {getattr(c, 'currency', '')}",
                            f"- **Trading Class**: {getattr(c, 'tradingClass', '')}",
                            f"- **Local Symbol**: {getattr(c, 'localSymbol', '')}",
                        ]
                    )

                # Multiple contracts - use table format
                headers = [
                    "ConID",
                    "Symbol",
                    "SecType",
                    "Exchange",
                    "Primary Exch",
                    "Currency",
                    "Trading Class",
                ]
                rows = []
                for c in contracts:
                    if c is None:
                        continue
                    rows.append(
                        [
                            str(getattr(c, "conId", "")),
                            str(getattr(c, "symbol", "")),
                            str(getattr(c, "secType", "")),
                            str(getattr(c, "exchange", "")),
                            str(getattr(c, "primaryExchange", "")),
                            str(getattr(c, "currency", "")),
                            str(getattr(c, "tradingClass", "")),
                        ]
                    )

                table = _format_markdown_table(headers, rows)
                return f"# Found {len(contracts)} contract(s) for {symbol}\n\n{table}"
            except Exception as e:  # pragma: no cover - depends on network
                return f"Error looking up contract: {e}"

        @self.server.tool(description="Convert ticker symbol to contract ID (conid)")
        async def ticker_to_conid(
            symbol: str,
            sec_type: str = "STK",
            exchange: str = "SMART",
            currency: str = "USD",
        ) -> str:
            await _ensure_connected()
            contract = _create_contract(symbol, sec_type, exchange, currency)
            try:
                contracts_raw = await self.ib.qualifyContractsAsync(contract)
                contracts = _flatten_contracts(contracts_raw)
                if not contracts:
                    return f"No contract found for {symbol}"
                conid = getattr(contracts[0], "conId", None)

                if len(contracts) == 1:
                    return f"**ConID for {symbol}**: {conid}"

                # Multiple contracts found
                result = [
                    f"# ConID for {symbol}",
                    f"**Primary ConID**: {conid}",
                    "",
                    f"**Note**: Found {len(contracts)} contracts. Using first one.",
                    "",
                    "## All ConIDs found:",
                ]

                contract_list = []
                for _, c in enumerate(contracts, 1):
                    if c is None:
                        continue
                    contract_list.append(
                        f"{getattr(c, 'conId', '')} "
                        f"({getattr(c, 'exchange', '')}, {getattr(c, 'currency', '')})"
                    )

                result.append(_format_markdown_list(contract_list, ordered=True))
                return "\n".join(result)
            except Exception as e:  # pragma: no cover
                return f"Error converting ticker to conid: {e}"

        @self.server.tool(description="Retrieve historical market data")
        async def get_historical_data(
            symbol: Annotated[str, "Stock symbol or conid"],
            duration: Annotated[str, "Duration (e.g., '1 M', '1 Y', '5 D')"] = "1 M",
            bar_size: Annotated[
                str, "Bar size (e.g., '1 day', '1 hour', '5 mins')"
            ] = "1 day",
            data_type: Annotated[
                str,
                "Data type (TRADES, MIDPOINT, BID, ASK, FEE_RATE, OPTION_IMPLIED_VOLATILITY)",
            ] = "TRADES",
            max_bars: Annotated[
                int,
                Field(description="Maximum number of bars to retrieve", ge=1, le=500),
            ] = 20,
            exchange: str = "SMART",
            currency: str = "USD",
        ) -> str:
            await _ensure_connected()
            contract = _create_contract(symbol, "STK", exchange, currency)
            try:
                contracts_raw = await self.ib.qualifyContractsAsync(contract)
                contracts = _flatten_contracts(contracts_raw)
                if not contracts:
                    return f"No contract found for {symbol}"
                c = contracts[0]
                bars = await self.ib.reqHistoricalDataAsync(
                    contract=c,
                    endDateTime="",
                    durationStr=duration,
                    barSizeSetting=bar_size,
                    whatToShow=data_type,
                    useRTH=True,
                )
                if not bars:
                    return f"No historical data found for {symbol}"

                headers = ["Date", "Open", "High", "Low", "Close", "Volume"]
                rows = []
                for bar in bars[-max_bars:]:
                    if hasattr(bar.date, "strftime"):
                        date_str = bar.date.strftime("%Y-%m-%d")  # type: ignore[attr-defined]
                    else:
                        date_str = str(bar.date)
                    rows.append(
                        [
                            date_str,
                            f"{bar.open:.2f}",
                            f"{bar.high:.2f}",
                            f"{bar.low:.2f}",
                            f"{bar.close:.2f}",
                            str(bar.volume),
                        ]
                    )

                table = _format_markdown_table(headers, rows)
                result = [
                    f"# Historical Data for {symbol} ({getattr(c, 'conId', '')})",
                    f"**Duration**: {duration} | **Bar Size**: {bar_size} | "
                    f"**Data Type**: {data_type}",
                    "",
                    table,
                ]

                if len(bars) > max_bars:
                    result.append(
                        f"\n*Showing last {max_bars} of {len(bars)} total bars*"
                    )

                return "\n".join(result)
            except Exception as e:  # pragma: no cover
                return f"Error getting historical data: {e}"

        @self.server.tool(
            description="Search for contracts by partial symbol or company name"
        )
        async def search_contracts(
            pattern: Annotated[str, "Search pattern (symbol or company name)"],
        ) -> str:
            await _ensure_connected()
            try:
                results = await self.ib.reqMatchingSymbolsAsync(pattern)
                if not results:
                    return f"No contracts found matching '{pattern}'"

                contract_items = []
                for desc in results[:10]:
                    c = desc.contract
                    if c is None:
                        continue
                    contract_items.append(
                        f"**{c.symbol}** ({c.conId}) - {c.secType} on "
                        f"{c.primaryExchange or c.exchange} ({c.currency})"
                    )

                result = [
                    f"# Contracts matching '{pattern}'",
                    "",
                    _format_markdown_list(contract_items, ordered=True),
                ]

                if len(results) > 10:
                    result.append(f"\n*... and {len(results) - 10} more results*")

                return "\n".join(result)
            except Exception as e:  # pragma: no cover
                return f"Error searching contracts: {e}"

        @self.server.tool(description="Retrieve historical news articles")
        async def get_historical_news(
            symbol: Annotated[str, "Stock symbol or conid"],
            start_date: Annotated[str, "Start date (YYYY-MM-DD)"],
            end_date: Annotated[str, "End date (YYYY-MM-DD)"],
            max_count: Annotated[int, "Maximum number of articles to retrieve"] = 10,
            exchange: Annotated[
                str, "Exchange (e.g., SMART, NYSE, NASDAQ, etc.)"
            ] = "SMART",
            currency: Annotated[str, "Currency (e.g., USD, EUR, etc.)"] = "USD",
        ) -> str:
            await _ensure_connected()
            contract = _create_contract(symbol, "STK", exchange, currency)
            try:
                contracts_raw = await self.ib.qualifyContractsAsync(contract)
                contracts = _flatten_contracts(contracts_raw)
                if not contracts:
                    return f"No contract found for {symbol}"
                c = contracts[0]
                news = await self.ib.reqHistoricalNewsAsync(
                    getattr(c, "conId", 0),
                    self.news_provider_codes,
                    start_date,
                    end_date,
                    max_count,
                )
                if not news:
                    return f"No historical news found for {symbol}"

                result = [
                    f"# Historical News for {symbol} ({getattr(c, 'conId', '')})",
                    f"**Period**: {start_date} to {end_date}",
                    "",
                ]

                if isinstance(news, list):
                    news_items = []
                    for article in news[:max_count]:
                        headline = getattr(article, "headline", "No headline")
                        time_str = getattr(article, "time", "No time")
                        provider = getattr(article, "providerCode", "Unknown provider")
                        article_id = getattr(article, "articleId", "No ID")

                        news_items.append(
                            f"**{headline}**  \n*{time_str}* | Provider: {provider} | "
                            f"ID: {article_id}"
                        )

                    result.append(_format_markdown_list(news_items, ordered=True))

                return "\n".join(result)
            except Exception as e:  # pragma: no cover
                return f"Error getting historical news: {e}"

        @self.server.tool(
            description="Retrieve a full news article by ID and provider code"
        )
        async def get_article(
            articleId: Annotated[str, "Article ID returned from historical news"],
            providerCode: Annotated[str, "Provider code returned from historical news"],
            as_markdown: Annotated[
                bool,
                "Attempt to convert XML content to markdown if the article is XML",
            ] = True,
            truncate: Annotated[
                int,
                "Optional max length of returned text (0 for no truncation)",
            ] = 0,
        ) -> str:
            await _ensure_connected()
            try:
                # Prefer async variant if available
                if hasattr(self.ib, "reqNewsArticleAsync"):
                    article_obj = await self.ib.reqNewsArticleAsync(providerCode, articleId)  # type: ignore[attr-defined]
                else:  # pragma: no cover - fallback path
                    article_obj = self.ib.reqNewsArticle(providerCode, articleId)  # type: ignore[attr-defined]
                if article_obj is None:
                    return f"No article content found for {providerCode}:{articleId}"
                raw_text = getattr(article_obj, "articleText", "") or getattr(
                    article_obj, "text", ""
                )
                if not raw_text:
                    return f"Article {providerCode}:{articleId} has no text content"
                if as_markdown:
                    formatted = _xml_to_markdown(raw_text)
                else:
                    formatted = raw_text
                if truncate and truncate > 0 and len(formatted) > truncate:
                    formatted = formatted[:truncate].rstrip() + "... *(truncated)*"
                return "\n".join(
                    [
                        f"# Article {articleId} ({providerCode})",
                        "",
                        formatted,
                    ]
                )
            except Exception as e:  # pragma: no cover
                return f"Error retrieving article {providerCode}:{articleId}: {e}"

        @self.server.tool(description="Retrieve fundamental data for a contract")
        async def get_fundamental_data(
            symbol: Annotated[str, "Stock symbol or conid"],
            report_type: Annotated[
                str,
                (
                    "Report type (ReportsFinSummary, ReportsOwnership, "
                    "ReportsFinStatements, RESC, CalendarReport)"
                ),
            ] = "ReportsFinSummary",
            exchange: str = "SMART",
            currency: str = "USD",
        ) -> str:
            await _ensure_connected()
            contract = _create_contract(symbol, "STK", exchange, currency)
            try:
                contracts_raw = await self.ib.qualifyContractsAsync(contract)
                contracts = _flatten_contracts(contracts_raw)
                if not contracts:
                    return f"No contract found for {symbol}"
                c = contracts[0]
                data = await self.ib.reqFundamentalDataAsync(c, report_type)
                if not data:
                    return f"No fundamental data found for {symbol}"
                formatted = _xml_to_markdown(data)
                lines = [
                    f"# Fundamental Data for {symbol} ({getattr(c, 'conId', '')})",
                    f"**Report Type**: {report_type}",
                    "",
                    formatted,
                ]
                return "\n".join(lines)
            except Exception as e:  # pragma: no cover
                return f"Error getting fundamental data: {e}"

        @self.server.tool(
            description="Retrieve portfolio positions and details. If this tool does "
            "not return results you can still use get_positions which may return results."
        )
        async def get_portfolio(
            account: Annotated[str, "Account name (empty for all accounts)"] = "",
        ) -> str:
            await _ensure_connected()
            try:
                items = self.ib.portfolio(account)
                if not items:
                    return "No portfolio items found"

                headers = [
                    "Symbol",
                    "Position",
                    "Avg Cost",
                    "Market Value",
                    "Unrealized PnL",
                ]
                rows = []
                for it in items:
                    rows.append(
                        [
                            str(it.contract.symbol),
                            str(it.position),
                            f"{it.averageCost:.2f}",
                            f"{it.marketValue:.2f}",
                            f"{it.unrealizedPNL:.2f}",
                        ]
                    )

                table = _format_markdown_table(headers, rows)
                account_title = (
                    f" for account {account}" if account else " (all accounts)"
                )
                return f"# Portfolio{account_title}\n\n{table}"
            except Exception as e:  # pragma: no cover
                return f"Error getting portfolio: {e}"

        @self.server.tool(description="Retrieve account summary information")
        async def get_account_summary(
            account: Annotated[str, "Account name (empty for all accounts)"] = "",
        ) -> str:
            await _ensure_connected()
            try:
                vals = await self.ib.accountSummaryAsync(account)
                if not vals:
                    return "No account data found"
                by_acc: dict[str, list[Any]] = {}
                for v in vals:
                    by_acc.setdefault(v.account, []).append(v)

                account_title = f" for {account}" if account else " (all accounts)"
                result = [f"# Account Summary{account_title}", ""]

                for acc, values in by_acc.items():
                    result.append(f"## Account: {acc}")
                    result.append("")

                    # Create markdown list of account values
                    account_items = []
                    for v in values:
                        account_items.append(f"**{v.tag}**: {v.value} {v.currency}")

                    result.append(_format_markdown_list(account_items))
                    result.append("")

                return "\n".join(result)
            except Exception as e:  # pragma: no cover
                return f"Error getting account summary: {e}"

        @self.server.tool(description="Retrieve current positions")
        async def get_positions(
            account: Annotated[str, "Account name (empty for all accounts)"] = "",
        ) -> str:
            await _ensure_connected()
            try:
                positions = self.ib.positions(account)
                if not positions:
                    return "No positions found"

                headers = ["Account", "Symbol", "Position", "Avg Cost"]
                rows = []
                for p in positions:
                    rows.append(
                        [
                            str(p.account),
                            str(p.contract.symbol),
                            str(p.position),
                            f"{p.avgCost:.2f}",
                        ]
                    )

                table = _format_markdown_table(headers, rows)
                account_title = (
                    f" for account {account}" if account else " (all accounts)"
                )
                return f"# Positions{account_title}\n\n{table}"
            except Exception as e:  # pragma: no cover
                return f"Error getting positions: {e}"

        @self.server.tool(
            description=(
                "Get detailed contract information including dividends and corporate actions"
            )
        )
        async def get_contract_details(
            symbol: Annotated[str, "Stock symbol or conid"],
            sec_type: str = "STK",
            exchange: str = "SMART",
            currency: str = "USD",
        ) -> str:
            await _ensure_connected()
            contract = _create_contract(symbol, sec_type, exchange, currency)
            try:
                contracts_raw = await self.ib.qualifyContractsAsync(contract)
                contracts = _flatten_contracts(contracts_raw)
                if not contracts:
                    return f"No contract found for {symbol}"
                c = contracts[0]
                details_list = await self.ib.reqContractDetailsAsync(c)
                if not details_list:
                    return f"No contract details found for {symbol}"
                d = details_list[0]
                lines = [
                    f"# Contract Details for {symbol} ({getattr(c, 'conId', '')})",
                    "",
                    "## Basic Information",
                    f"- **Long Name**: {getattr(d, 'longName', '')}",
                    f"- **Industry**: {getattr(d, 'industry', '')}",
                    f"- **Category**: {getattr(d, 'category', '')}",
                    f"- **Subcategory**: {getattr(d, 'subcategory', '')}",
                    f"- **Market Name**: {getattr(d, 'marketName', '')}",
                    f"- **Trading Hours**: {getattr(d, 'tradingHours', '')}",
                    f"- **Liquid Hours**: {getattr(d, 'liquidHours', '')}",
                    "",
                    "## Financial Information",
                    f"- **Min Tick**: {getattr(d, 'minTick', '')}",
                    f"- **Price Magnifier**: {getattr(d, 'priceMagnifier', '')}",
                    f"- **Market Cap**: {getattr(d, 'marketCap', 'N/A')}",
                    f"- **Shares Outstanding**: {getattr(d, 'sharesOutstanding', 'N/A')}",
                ]

                # Dividends if available
                dividends = getattr(d, "dividends", None)
                if dividends:
                    lines.append("")
                    lines.append("## Recent Dividends")
                    dividend_items = []
                    for div in dividends[:5]:
                        if div is not None:
                            dividend_items.append(
                                f"{getattr(div, 'date', '')}: "
                                f"${getattr(div, 'amount', '')} ({getattr(div, 'currency', '')})"
                            )
                    lines.append(_format_markdown_list(dividend_items))

                return "\n".join(lines)
            except Exception as e:  # pragma: no cover
                return f"Error getting contract details: {e}"

        # Keep references on self to make tools reachable in tests/REPL if needed
        self.lookup_contract = lookup_contract  # type: ignore[attr-defined]
        self.ticker_to_conid = ticker_to_conid  # type: ignore[attr-defined]
        self.get_historical_data = get_historical_data  # type: ignore[attr-defined]
        self.search_contracts = search_contracts  # type: ignore[attr-defined]
        self.get_historical_news = get_historical_news  # type: ignore[attr-defined]
        self.get_fundamental_data = get_fundamental_data  # type: ignore[attr-defined]
        self.get_portfolio = get_portfolio  # type: ignore[attr-defined]
        self.get_account_summary = get_account_summary  # type: ignore[attr-defined]
        self.get_positions = get_positions  # type: ignore[attr-defined]
        self.get_contract_details = get_contract_details  # type: ignore[attr-defined]

    def run(
        self,
        transport: str = "stdio",
        http_host: str = "127.0.0.1",
        http_port: int = 8000
    ) -> None:
        """Run the FastMCP server (synchronous).

        Args:
            transport: Transport type ("stdio" or "http")
            http_host: Host to bind HTTP server to (if transport="http")
            http_port: Port to bind HTTP server to (if transport="http")
        """
        logging.basicConfig(level=logging.INFO)

        # Log startup configuration
        if transport == "http":
            logger.info("IB-MCP transport=http http=%s:%s", http_host, http_port)
        else:
            logger.info("IB-MCP transport=stdio")

        try:
            # FastMCP's run manages its own event loop using anyio.run internally.
            if transport == "http":
                # Use streamable-http transport for HTTP mode
                self.server.run(transport="streamable-http", host=http_host, port=http_port)
            else:
                # Default STDIO transport
                self.server.run()
        finally:  # pragma: no cover - disconnect path is runtime-only
            if self.connected:
                self.ib.disconnect()
                self.connected = False


def main() -> None:
    """CLI entry point for running the server."""
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="Interactive Brokers MCP Server (FastMCP)"
    )

    # IB connection parameters
    parser.add_argument(
        "--host",
        default=os.getenv("IB_HOST", "127.0.0.1"),
        help="IB Gateway/TWS host (env: IB_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("IB_PORT", "7497")),
        help="IB Gateway/TWS port (env: IB_PORT)",
    )
    parser.add_argument(
        "--client-id",
        type=int,
        default=int(os.getenv("IB_CLIENT_ID", "1")),
        help="Client ID (env: IB_CLIENT_ID)",
    )

    # Transport configuration
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.getenv("IB_MCP_TRANSPORT", "stdio"),
        help="Transport protocol (stdio or http) (env: IB_MCP_TRANSPORT)",
    )
    parser.add_argument(
        "--http-host",
        default=os.getenv("IB_MCP_HTTP_HOST", "127.0.0.1"),
        help="HTTP server host (env: IB_MCP_HTTP_HOST)",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=int(os.getenv("IB_MCP_HTTP_PORT", "8000")),
        help="HTTP server port (env: IB_MCP_HTTP_PORT)",
    )

    args = parser.parse_args()

    server = IBMCPServer(args.host, args.port, args.client_id)
    server.run(transport=args.transport, http_host=args.http_host, http_port=args.http_port)


__all__ = ["IBMCPServer", "main"]


if __name__ == "__main__":
    main()
