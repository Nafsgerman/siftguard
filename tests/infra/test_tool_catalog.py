"""T22: Tool catalog exists, is current, and covers all MCP tools."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "docs" / "tool_catalog.md"
sys.path.insert(0, str(REPO_ROOT / "src"))


def test_catalog_exists() -> None:
    assert CATALOG.exists(), (
        "docs/tool_catalog.md missing — run: python scripts/generate_tool_catalog.py"
    )


def test_catalog_has_table_header() -> None:
    text = CATALOG.read_text()
    assert "| Tool | Description | Required Parameters | Optional Parameters |" in text


def test_catalog_covers_all_tools() -> None:
    from siftguard.mcp_server.server import TOOLS

    text = CATALOG.read_text()
    for tool in TOOLS:
        assert f"`{tool.name}`" in text, f"Tool '{tool.name}' missing from catalog"


def test_catalog_not_empty() -> None:
    from siftguard.mcp_server.server import TOOLS

    assert len(TOOLS) >= 8, f"Expected ≥8 tools, got {len(TOOLS)}"
