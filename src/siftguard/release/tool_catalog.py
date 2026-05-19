"""Tool catalog generator — introspects TOOLS from mcp_server/server.py and emits docs/TOOL_CATALOG.md."""
from __future__ import annotations

import json
from pathlib import Path

from siftguard.mcp_server.server import TOOLS

CATALOG_PATH = Path("docs/TOOL_CATALOG.md")


def _schema_to_table(schema: dict) -> str:
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    if not props:
        return "_No inputs._\n"
    rows = [
        "| Parameter | Type | Required | Default | Notes |",
        "|-----------|------|:--------:|---------|-------|",
    ]
    for param, spec in props.items():
        ptype = f"`{spec.get('type', 'any')}`"
        req = "✓" if param in required else ""
        default = spec.get("default", "")
        default_str = f"`{default}`" if default != "" else ""
        notes = spec.get("description", "")
        rows.append(f"| `{param}` | {ptype} | {req} | {default_str} | {notes} |")
    return "\n".join(rows) + "\n"


def _example(tool_name: str, schema: dict) -> str:
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    placeholders = {
        "memory_image": "/cases/TEST-001/base-hunt-memory.img",
        "evidence_path": "/cases/TEST-001/base-hunt-memory.img",
        "image_path": "/cases/TEST-001/disk.img",
        "hive_path": "/cases/TEST-001/hives/SYSTEM",
        "plaso_file": "/tmp/siftguard_timeline.plaso",
        "output_csv": "/tmp/siftguard_sorted.csv",
        "output_plaso": "/tmp/siftguard_timeline.plaso",
        "output_path": "/tmp/extracted_file",
        "inode": "12345-128-1",
        "offset": "2048",
    }
    args: dict = {}
    for param in required:
        spec = props.get(param, {})
        ptype = spec.get("type", "string")
        if param in placeholders:
            args[param] = placeholders[param]
        elif ptype == "boolean":
            args[param] = False
        elif ptype == "integer":
            args[param] = 0
        else:
            args[param] = f"<{param}>"
    return f"```json\n{json.dumps({'tool': tool_name, 'arguments': args}, indent=2)}\n```"


def generate() -> str:
    """Return full catalog markdown as a string (no file I/O)."""
    lines: list[str] = [
        "# SIFTGuard Tool Catalog",
        "",
        "> Auto-generated from `src/siftguard/mcp_server/server.py`.",
        "> Do **not** edit manually — run `make tool-catalog` to regenerate.",
        "",
        f"**{len(TOOLS)} forensic tools registered.** All tools are READ-ONLY.",
        "Evidence integrity is enforced architecturally — destructive operations do not exist.",
        "",
        "## Index",
        "",
    ]
    for tool in TOOLS:
        anchor = tool.name.replace("_", "-")
        lines.append(f"- [`{tool.name}`](#{anchor})")
    lines += ["", "---", ""]
    for tool in TOOLS:
        lines += [
            f"## {tool.name}",
            "",
            f"**Description:** {tool.description}",
            "",
            "### Input Schema",
            "",
            _schema_to_table(tool.inputSchema),
            "",
            "### Output",
            "",
            "Returns [`ForensicResult`](../src/siftguard/models/forensic.py) serialized as JSON.",
            "Key fields: `tool` · `findings` · `evidence_refs` · `duration_ms` · `outcome` (`ok` | `partial` | `fail`)",
            "",
            "### Example Invocation",
            "",
            _example(tool.name, tool.inputSchema),
            "",
            "---",
            "",
        ]
    return "\n".join(lines)


def main() -> None:
    catalog = generate()
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(catalog, encoding="utf-8")
    print(f"✓ Wrote {CATALOG_PATH} ({len(TOOLS)} tools)")


if __name__ == "__main__":
    main()