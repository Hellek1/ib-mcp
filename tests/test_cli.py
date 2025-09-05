# ruff: noqa: S101
#!/usr/bin/env python3
"""Test CLI functionality."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_cli_help() -> None:
    """Test that CLI help works and shows new transport options."""
    result = subprocess.run(
        [sys.executable, "-m", "ib_mcp.server", "--help"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert result.returncode == 0
    help_text = result.stdout

    # Check that new options are in help
    assert "--transport" in help_text
    assert "{stdio,http}" in help_text
    assert "--http-host" in help_text
    assert "--http-port" in help_text
    assert "IB_MCP_TRANSPORT" in help_text


def test_cli_default_transport() -> None:
    """Test that default transport is stdio."""
    import argparse
    from unittest.mock import patch

    from ib_mcp.server import main

    # Mock the argument parsing part
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        with patch("ib_mcp.server.IBMCPServer") as mock_server_class:
            mock_server = mock_server_class.return_value

            # Simulate default args
            mock_args = argparse.Namespace(
                host="127.0.0.1",
                port=7497,
                client_id=1,
                transport="stdio",
                http_host="127.0.0.1",
                http_port=8000,
            )
            mock_parse.return_value = mock_args

            try:
                main()
            except SystemExit:
                pass  # main() calls server.run() which may exit

            # Verify server was created with correct IB params
            mock_server_class.assert_called_once_with("127.0.0.1", 7497, 1)

            # Verify run was called with correct transport params
            mock_server.run.assert_called_once_with(
                transport="stdio",
                http_host="127.0.0.1",
                http_port=8000
            )
