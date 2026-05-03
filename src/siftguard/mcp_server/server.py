from __future__ import annotations
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from siftguard.mcp_server.tools.mft import analyze_mft, scan_mft_ads
from siftguard.mcp_server.tools.volatility import vol_pslist, vol_netscan, vol_malfind
from siftguard.mcp_server.tools.timeline import create_supertimeline, sort_timeline
from siftguard.mcp_server.tools.registry import run_regripper, list_registry_hives, query_registry_key, hunt_registry
from siftguard.mcp_server.tools.filesystem import list_files, extract_file

app = Server("siftguard-mcp")

TOOLS = [
    Tool(name="analyze_mft",
         description="Parse Windows $MFT. Returns typed entries with timestomp flags. READ-ONLY.",
         inputSchema={"type":"object","properties":{"memory_image":{"type":"string"},"timestomp_only":{"type":"boolean","default":False}},"required":["memory_image"]}),
    Tool(name="vol_pslist",
         description="List processes from memory image. Flags suspicious names and parent-child combos. READ-ONLY.",
         inputSchema={"type":"object","properties":{"memory_image":{"type":"string"}},"required":["memory_image"]}),
    Tool(name="vol_netscan",
         description="Scan memory image for network connections. READ-ONLY.",
         inputSchema={"type":"object","properties":{"memory_image":{"type":"string"}},"required":["memory_image"]}),
    Tool(name="vol_malfind",
         description="Find injected code and suspicious memory regions. READ-ONLY.",
         inputSchema={"type":"object","properties":{"memory_image":{"type":"string"}},"required":["memory_image"]}),
    Tool(name="create_supertimeline",
         description="Run log2timeline to build a plaso supertimeline from evidence. READ-ONLY.",
         inputSchema={"type":"object","properties":{"evidence_path":{"type":"string"},"output_plaso":{"type":"string","default":"/tmp/siftguard_timeline.plaso"}},"required":["evidence_path"]}),
    Tool(name="sort_timeline",
         description="Run psort to produce a sorted CSV timeline from a plaso file. READ-ONLY.",
         inputSchema={"type":"object","properties":{"plaso_file":{"type":"string"},"output_csv":{"type":"string","default":"/tmp/siftguard_sorted.csv"},"filter_date_start":{"type":"string"}},"required":["plaso_file"]}),
    Tool(name="run_regripper",
         description="Run a regripper plugin against a registry hive. Approved plugins: autoruns, services, run, userassist, shellbags, recentdocs, networklist, timezone, samparse. READ-ONLY.",
         inputSchema={"type":"object","properties":{"hive_path":{"type":"string"},"plugin":{"type":"string","default":"autoruns"}},"required":["hive_path"]}),
    Tool(name="list_files",
         description="List files in a disk image using fls (TSK). Recovers deleted files. READ-ONLY.",
         inputSchema={"type":"object","properties":{"image_path":{"type":"string"},"offset":{"type":"string","default":""},"recursive":{"type":"boolean","default":True}},"required":["image_path"]}),
    Tool(name="extract_file",
         description="Extract a file from a disk image by inode using icat. READ-ONLY.",
         inputSchema={"type":"object","properties":{"image_path":{"type":"string"},"inode":{"type":"string"},"output_path":{"type":"string"},"offset":{"type":"string","default":""}},"required":["image_path","inode","output_path"]}),
]

DISPATCH = {
    "analyze_mft": lambda a: analyze_mft(**a),
    "vol_pslist": lambda a: vol_pslist(**a),
    "vol_netscan": lambda a: vol_netscan(**a),
    "vol_malfind": lambda a: vol_malfind(**a),
    "create_supertimeline": lambda a: create_supertimeline(**a),
    "sort_timeline": lambda a: sort_timeline(**a),
    "run_regripper": lambda a: run_regripper(**a),
    "list_files": lambda a: list_files(**a),
    "extract_file": lambda a: extract_file(**a),
}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = DISPATCH.get(name)
    if not handler:
        raise ValueError(f"unknown tool: {name}")
    result = await handler(arguments)
    return [TextContent(type="text", text=result.model_dump_json(indent=2))]


def main() -> None:
    asyncio.run(_run())


async def _run() -> None:
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    main()
