# IB Async MCP Server

[![CI](https://github.com/Hellek1/ib-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Hellek1/ib-mcp/actions/workflows/ci.yml)

Lightweight Model Context Protocol (MCP) server exposing read-only Interactive Brokers data (contracts, historical data, fundamentals, news, portfolio, account) via the asynchronous [`ib_async`](https://ib-api-reloaded.github.io/ib_async/) library and [`FastMCP`](https://github.com/modelcontextprotocol/fastmcp). Ideal for feeding financial data into LLM workflows and autonomous agents while keeping trading disabled.

## Overview

This directory contains an MCP (Model Context Protocol) server that wraps the ib_async library to allow LLMs to interact with Interactive Brokers data.

## Features

The MCP server provides the following tools for LLM interaction:

### 1. Contract Lookup and Conversion
- **lookup_contract**: Look up contract details by ticker symbol and optional exchange/currency
- **ticker_to_conid**: Convert ticker symbol to contract ID (conid)

### 2. Market Data
- **get_historical_data**: Retrieve historical market data with configurable duration, bar size, and data type

### 3. News
- **get_news**: Retrieve current news articles for a contract
- **get_historical_news**: Retrieve historical news articles within a date range

### 4. Fundamental Data
- **get_fundamental_data**: Retrieve fundamental data including financial summaries, ownership, financial statements, and more

### 5. Portfolio and Account Information
- **get_portfolio**: Retrieve portfolio positions and details
- **get_account_summary**: Retrieve account summary information
- **get_positions**: Retrieve current positions

## Prerequisites

1. **Interactive Brokers Account**: You need an active IB account
2. **IB Gateway or TWS**: Download and install either:
   - [IB Gateway (Stable)](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php) - Recommended for API-only use
   - [IB Gateway (Latest)](https://www.interactivebrokers.com/en/trading/ibgateway-latest.php) - Latest features
   - [Trader Workstation (TWS)](https://www.interactivebrokers.com/en/trading/tws.php) - Full trading platform

3. **API Configuration**:
   - Enable API access in TWS/Gateway: `Configure → API → Settings` and check "Enable ActiveX and Socket Clients"
   - Set appropriate port (default: 7497 for TWS, 4001 for Gateway)
   - Add `127.0.0.1` to trusted IPs if connecting locally

## Installation

### From source (development)
```bash
git clone https://github.com/Hellek1/ib-mcp.git
cd ib-mcp
pip install poetry
poetry install
```

## Usage

### Running the MCP Server

```bash
# Using default settings (TWS on localhost:7497)
poetry run ib-mcp-server

# Custom IB Gateway connection
poetry run ib-mcp-server --host 127.0.0.1 --port 4001 --client-id 1

# Help with all options
poetry run ib-mcp-server --help
```

### Command Line Options

- `--host`: IB Gateway/TWS host (default: 127.0.0.1)
- `--port`: IB Gateway/TWS port (default: 7497 for TWS, use 4001 for Gateway)
- `--client-id`: Unique client ID for the connection (default: 1)

You can also use environment variables instead of flags:

- `IB_HOST`
- `IB_PORT`
- `IB_CLIENT_ID`

Flags override environment variables if both are provided.

## Docker

### Build

```bash
docker build -t ib-mcp .
```

### Run (connect to TWS running on host)

On macOS/Windows Docker Desktop you can reach host via `host.docker.internal` (already the default):

```bash
docker run --rm -it \
   -e IB_HOST=host.docker.internal \
   -e IB_PORT=7497 \
   -e IB_CLIENT_ID=1 \
   ghcr.io/hellek1/ib-mcp
```

On Linux you may need to add `--add-host host.docker.internal:host-gateway` and ensure the TWS/Gateway port is accessible:

```bash
docker run --rm -it \
   --add-host host.docker.internal:host-gateway \
   -e IB_HOST=host.docker.internal \
   -e IB_PORT=7497 \
   ghcr.io/hellek1/ib-mcp
```

Override arguments directly if preferred:

```bash
docker run --rm -it ghcr.io/hellek1/ib-mcp --host host.docker.internal --port 4001 --client-id 2
```


### MCP Client Integration

The server communicates via stdio using the MCP protocol. It can be integrated with MCP-compatible tools and LLM applications.

Example MCP client configuration (e.g. Claude Desktop) using Docker:
```json
{
   "mcpServers": {
      "ib-async": {
         "command": "docker",
         "args": [
            "run",
            "--rm",
            "--add-host","host.docker.internal:host-gateway",
            "-e","IB_HOST=host.docker.internal",
            "-e","IB_PORT=7497",
            "-e","IB_CLIENT_ID=1",
            "ghcr.io/hellek1/ib-mcp:latest"
         ]
      }
   }
}
```

Notes:
1. Remove the `--add-host` line on macOS/Windows Docker Desktop (it's only needed on Linux).

## Available Tools

### Contract Lookup
```
lookup_contract(symbol, sec_type="STK", exchange="SMART", currency="USD")
ticker_to_conid(symbol, sec_type="STK", exchange="SMART", currency="USD")
```

### Market Data
```
get_historical_data(symbol, duration="1 M", bar_size="1 day", data_type="TRADES", exchange="SMART", currency="USD")
```

### News
```
get_news(symbol, provider_codes="", exchange="SMART", currency="USD")
get_historical_news(symbol, start_date, end_date, provider_codes="", max_count=10, exchange="SMART", currency="USD")
```

### Fundamentals
```
get_fundamental_data(symbol, report_type="ReportsFinSummary", exchange="SMART", currency="USD")
```

Available report types:
- `ReportsFinSummary`: Financial summary
- `ReportsOwnership`: Ownership information
- `ReportsFinStatements`: Financial statements
- `RESC`: Research reports
- `CalendarReport`: Calendar events

### Portfolio & Account
```
get_portfolio(account="")
get_account_summary(account="")
get_positions(account="")
```

## Example Usage

Once connected to an LLM through MCP, you can ask questions like:

- "Look up the contract details for AAPL"
- "Get the last month of daily historical data for TSLA"
- "What are the recent news articles for Microsoft?"
- "Show me the financial summary for Google"
- "What positions do I currently have in my portfolio?"

## Data Formats

### XML to Markdown Conversion

The server automatically converts XML-formatted fundamental data to markdown for better readability in LLM interactions.

### Error Handling

The server includes comprehensive error handling and will provide meaningful error messages when:
- IB connection fails
- Invalid symbols are requested
- Market data is not available
- Authentication issues occur

## Troubleshooting

### Connection Issues

1. **"Cannot connect to Interactive Brokers"**
   - Ensure TWS/Gateway is running
   - Check that API is enabled in settings
   - Verify port numbers match (7497 for TWS, 4001 for Gateway)
   - Check firewall settings

2. **"No contract found"**
   - Verify symbol spelling
   - Try different exchanges (NYSE, NASDAQ vs SMART)
   - Check if security type is correct

3. **"No market data"**
   - Ensure you have appropriate market data subscriptions
   - Check if markets are open for real-time data
   - Try delayed data mode if real-time is not available

### Performance Tips

1. Use specific exchanges when possible instead of "SMART" routing
2. Limit historical data requests to reasonable time ranges
3. Cache contract IDs for frequently accessed symbols

## Security Considerations

- The MCP server operates in read-only mode - no order placement capabilities
- Credentials are handled by the IB Gateway/TWS application
- The server only accesses data you have permission to view in your IB account

## Contributing

1. Fork & branch: `feat/xyz`
2. Install dev deps: `poetry install`
3. Activate pre-commit: `pre-commit install`
4. Run tests: `poetry run pytest -q`
5. Open a PR with a concise description.

### Release (maintainers)
```bash
poetry version patch  # or minor / major
poetry build
poetry publish --username __token__ --password <pypi-token>
git tag v$(poetry version -s)
git push --tags
```

## Support & References

- IB API functionality: [ib_async docs](https://ib-api-reloaded.github.io/ib_async/)
- MCP protocol: [MCP spec](https://spec.modelcontextprotocol.io/)
- Interactive Brokers: [IB API docs](https://ibkrcampus.com/ibkr-api-page/twsapi-doc/)

---

Licensed under the BSD 3-Clause License. Contributions welcome.
