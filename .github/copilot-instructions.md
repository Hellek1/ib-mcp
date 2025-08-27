# Copilot Instructions for IB-MCP

This repository contains an Interactive Brokers MCP (Model Context Protocol) server that provides read-only access to Interactive Brokers data via the async `ib_async` library and `FastMCP` framework.

## Project Overview

**Purpose**: Expose Interactive Brokers financial data to LLM applications and autonomous agents through the MCP protocol, maintaining read-only access for safety.

**Key Technologies**:
- Python 3.12+ (modern Python features expected)
- FastMCP framework for MCP protocol implementation
- ib_async for Interactive Brokers API integration
- Poetry for dependency management
- Async/await patterns throughout

## Architecture

### Core Components
- `ib_mcp/server.py`: Main MCP server implementation using FastMCP
- `IBMCPServer`: Primary server class that manages IB connection and tool registration
- Tools: Contract lookup, market data, news, fundamentals, portfolio/account info

### MCP Tools Pattern
Tools are registered using FastMCP decorators within `_register_handlers()` method:
```python
@self.server.tool
async def tool_name(
    param: Annotated[str, Field(description="Parameter description")]
) -> str:
    await _ensure_connected()
    # Tool implementation
    return "human-readable result string"
```

## Coding Standards & Conventions

### Python Standards
- **Python Version**: 3.12+ required, use modern syntax (list[T], dict[K,V] over typing equivalents)
- **Type Hints**: Required for all public functions, prefer built-in generics
- **Async/Await**: All IB API calls must be async, use `await self.ib.someMethodAsync()`
- **Error Handling**: Catch broad exceptions only at integration boundaries, re-raise with context

### Code Style
- **Formatter**: Ruff (handles both imports and formatting)
- **Line Length**: 100 characters
- **Quotes**: Double quotes preferred
- **Import Order**: Managed by Ruff

### Project Conventions
- **Tool Returns**: Always return plain strings, prefer human-readable tables/bullet lists
- **Parameter Docs**: Use `Annotated[Type, Field(description="...")]` for tool parameters
- **Connection Management**: Use `_ensure_connected()` before IB API calls
- **XML Processing**: Convert XML responses to Markdown for better LLM readability

## Development Workflow

### Setup
```bash
pip install poetry
poetry install
pre-commit install  # Sets up git hooks
```

### Development Loop
```bash
poetry run ruff check .        # Lint code
poetry run mypy ib_mcp         # Type checking
poetry run pytest -q          # Run tests
```

### Pre-commit Hooks
- Ruff formatting and linting
- MyPy type checking
- Secret detection
- File validation

## Testing Patterns

### Current Test Structure
- Light testing approach (no live IB connections in tests)
- Mock IB API responses for unit tests
- Integration tests marked and skipped by default

### Adding Tests
- Unit tests for pure helper functions
- Mock network-dependent logic
- Mark integration tests with appropriate decorators

## Common Patterns

### Tool Registration
```python
@self.server.tool
async def get_something(
    symbol: Annotated[str, Field(description="Stock symbol")],
    exchange: Annotated[str, Field(description="Exchange")] = "SMART",
) -> str:
    await _ensure_connected()
    contract = ib.Stock(symbol, exchange)
    result = await self.ib.someMethodAsync(contract)
    return format_result_as_text(result)
```

### Contract Creation
```python
contract = ib.Stock(symbol, exchange, currency)  # For stocks
contract = ib.Future(symbol, lastTradeDateOrContractMonth, exchange)  # For futures
```

### Error Handling
```python
try:
    result = await self.ib.someMethodAsync(contract)
    if not result:
        return f"No data found for {symbol}"
except Exception as e:
    logger.error("Failed to fetch data: %s", e)
    return f"Error fetching data for {symbol}: {e}"
```

### XML to Markdown Conversion
The codebase includes utilities to convert XML fundamental data to Markdown:
```python
def _xml_element_to_markdown(element: ET.Element, level: int = 0) -> str:
    # Converts XML structure to readable Markdown format
```

## FastMCP Specifics

- Use `FastMCP("Server Name")` for server creation
- Tools auto-generate JSON schemas from type hints
- Server handles MCP protocol details automatically
- Focus on tool logic, not MCP plumbing

## Interactive Brokers API Notes

### Connection
- Always use `readonly=True` for safety
- Default ports: TWS (7497), Gateway (4001)
- Handle connection state with `self.connected` flag

### Common IB Async Methods
- `connectAsync()`: Establish connection
- `qualifyContractsAsync()`: Validate and get contract details
- `reqHistoricalDataAsync()`: Get historical data
- `reqFundamentalDataAsync()`: Get fundamental data
- `reqNewsProvidersAsync()`: Get available news providers
- `reqHistoricalNewsAsync()`: Get historical news

### Data Formatting
- Return human-readable strings from tools
- Use tables, bullet points, or structured text
- Convert numeric data to readable formats
- Handle empty/null responses gracefully

## Security Considerations

- **Read-only mode**: All IB connections use `readonly=True`
- **No trading**: Server cannot place orders or modify positions
- **Credential handling**: IB Gateway/TWS manages authentication
- **Input validation**: Sanitize user inputs, especially for XML processing

## Adding New Tools

1. Define async function within `_register_handlers()`
2. Use `@self.server.tool` decorator
3. Add typed parameters with `Annotated[Type, Field(description="...")]`
4. Implement `await _ensure_connected()` at start
5. Return human-readable string
6. Update README if user-visible capability
7. Store reference on `self` for testability: `self.tool_name = tool_name`

## Contribution Guidelines

- Follow existing patterns for consistency
- Minimal dependencies (keep it lightweight)
- Comprehensive error handling and logging
- Human-readable outputs optimized for LLM consumption
- No breaking changes to existing tool signatures
- Update documentation for new user-visible features

## Common Pitfalls to Avoid

- Don't use blocking IB API calls (always use `*Async` methods)
- Don't forget `await _ensure_connected()` in tools
- Don't return complex objects from tools (strings only)
- Don't catch exceptions too broadly without re-raising with context
- Don't use deprecated `typing.List`/`typing.Dict` (use built-in `list`/`dict`)