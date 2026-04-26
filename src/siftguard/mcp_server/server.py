from __future__ import annotations
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from siftguard.mcp_server.tools.mft import analyze_mft

app = Server("siftguard-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="analyze_mft",
            description=(
                "Parse a Windows $MFT file. Returns typed entries with SI/FN timestamps "
                "and timestomp suspicion flags. READ-ONLY."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mft_path": {"type": "string"},
                    "output_csv": {"type": "string", "default": "/tmp/siftguard_mft.csv"},
                    "timestomp_only": {"type": "boolean", "default": False},
                },
                "required": ["mft_path"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "analyze_mft":
        result = await analyze_mft(**arguments)
        return [TextContent(type="text", text=result.model_dump_json(indent=2))]
    raise ValueError(f"unknown tool: {name}")


def main() -> None:
    asyncio.run(_run())


async def _run() -> None:
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    main()
