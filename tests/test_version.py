# ruff: noqa: S101
"""The version reported to MCP clients must match the package version."""

import tomllib
from pathlib import Path

from ib_mcp import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_version_matches_pyproject() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert __version__ == pyproject["tool"]["poetry"]["version"], (
        "ib_mcp/__init__.py __version__ is out of sync with pyproject.toml; "
        "update it after `poetry version`"
    )
