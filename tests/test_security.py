import sys
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Mock dependencies before importing server
mock_ib_async = MagicMock()
mock_fastmcp = MagicMock()
mock_defusedxml = MagicMock()
mock_pydantic = MagicMock()

# Mock FastMCP.tool decorator
def mock_tool(*args, **kwargs):
    def decorator(f):
        return f
    return decorator

mock_fastmcp.FastMCP.return_value.tool = mock_tool

class MockIB:
    def __init__(self):
        self.accountSummaryAsync = AsyncMock()
        self.qualifyContractsAsync = AsyncMock()
        self.connectAsync = AsyncMock()
        self.reqNewsProvidersAsync = AsyncMock(return_value=[])
        self.positions = MagicMock()

mock_ib_async.IB = MockIB
mock_ib_async.Contract = MagicMock
mock_ib_async.Stock = MagicMock

sys.modules['ib_async'] = mock_ib_async
sys.modules['fastmcp'] = mock_fastmcp
sys.modules['defusedxml'] = mock_defusedxml
sys.modules['defusedxml.ElementTree'] = mock_defusedxml.ElementTree
sys.modules['pydantic'] = mock_pydantic

from ib_mcp.server import IBMCPServer

async def test_error_handling_sanitization():
    """Verify that internal exception details are not exposed to the user."""
    server = IBMCPServer()
    server.connected = True

    # 1. Test get_account_summary
    server.ib.accountSummaryAsync.side_effect = Exception("Internal DB error")
    result = await server.get_account_summary()
    assert "Internal DB error" not in result
    assert "An internal error occurred" in result

    # 2. Test lookup_contract
    server.ib.qualifyContractsAsync.side_effect = Exception("Connectivity issue detail")
    result = await server.lookup_contract("AAPL")
    assert "Connectivity issue detail" not in result
    assert "An internal error occurred" in result

    # 3. Test _ensure_connected
    server.connected = False
    server.ib.connectAsync.side_effect = Exception("Network timeout trace")

    # _ensure_connected is internal, but we can test it through a tool that calls it.
    # lookup_contract calls _ensure_connected BEFORE its own try-except block.
    try:
        await server.lookup_contract("AAPL")
        pytest_fail = True
    except ConnectionError as e:
        pytest_fail = False
        assert "Network timeout trace" not in str(e)
        assert "An internal error occurred" in str(e)
    except Exception:
        pytest_fail = True

    if pytest_fail:
        raise AssertionError("Should have raised ConnectionError during connection failure")

if __name__ == "__main__":
    asyncio.run(test_error_handling_sanitization())
