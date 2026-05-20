#!/usr/bin/env python3
"""T22: Generate docs/tool_catalog.md from MCP server TOOLS list."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from siftguard.mcp_server.server import TOOLS  # noqa: E402

OUTFILE = REPO_ROOT / "docs" / "tool_catalog.md"

HEADER = """\
# SIFTGuard Tool Catalog

Auto-generated from `src/siftguard/mcp_server/server.py`. Do not edit manually.
Run `python scripts/generate_tool_catalog.py` to regenerate.

| Tool | Description | Required Parameters | Optional Parameters |
|------|-------------|---------------------|---------------------|
"""


def _params(schema: dict) -> tuple[str, str]:
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    req, opt = [], []
    for name, spec in props.items():
        typ = spec.get("type", "any")
        entry = f"`{name}` ({typ})"
        (req if name in required else opt).append(entry)
    return ", ".join(req) or "—", ", ".join(opt) or "—"


def main() -> None:
    rows = []
    for tool in TOOLS:
        schema = (
            tool.inputSchema if isinstance(tool.inputSchema, dict) else json.loads(tool.inputSchema)
        )
        req, opt = _params(schema)
        desc = tool.description.replace("|", "\\|")
        rows.append(f"| `{tool.name}` | {desc} | {req} | {opt} |")

    OUTFILE.parent.mkdir(parents=True, exist_ok=True)
    OUTFILE.write_text(HEADER + "\n".join(rows) + "\n")
    print(f"✓ Wrote {len(rows)} tools → {OUTFILE}")


if __name__ == "__main__":
    main()
