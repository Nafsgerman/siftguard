"""T22 — asserts every MCP-registered tool appears in the generated catalog."""

from __future__ import annotations

import pytest

from siftguard.mcp_server.server import TOOLS
from siftguard.release.tool_catalog import CATALOG_PATH, generate


def test_all_registered_tools_in_catalog():
    catalog = generate()
    missing = [t.name for t in TOOLS if t.name not in catalog]
    assert not missing, f"Tools missing from generated catalog: {missing}"


def test_catalog_header_present():
    assert "# SIFTGuard Tool Catalog" in generate()


def test_tool_count_line():
    catalog = generate()
    assert f"**{len(TOOLS)} forensic tools registered.**" in catalog


def test_each_tool_has_section_header():
    catalog = generate()
    for tool in TOOLS:
        assert f"## {tool.name}" in catalog, f"Section header missing: {tool.name}"


def test_each_tool_has_input_schema_section():
    catalog = generate()
    for tool in TOOLS:
        idx = catalog.index(f"## {tool.name}")
        section = catalog[idx : idx + 800]
        assert "### Input Schema" in section, f"Input schema missing: {tool.name}"


def test_each_tool_has_example_invocation():
    catalog = generate()
    for tool in TOOLS:
        idx = catalog.index(f"## {tool.name}")
        section = catalog[idx : idx + 800]
        assert "### Example Invocation" in section, f"Example missing: {tool.name}"


def test_catalog_file_exists_after_generation():
    """On-disk check — requires `make tool-catalog` to have run."""
    if not CATALOG_PATH.exists():
        pytest.skip("TOOL_CATALOG.md not generated yet — run `make tool-catalog`")
    content = CATALOG_PATH.read_text(encoding="utf-8")
    missing = [t.name for t in TOOLS if t.name not in content]
    assert not missing, f"Stale catalog on disk: {missing}. Run `make tool-catalog`."
