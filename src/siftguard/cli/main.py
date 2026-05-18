from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

app = typer.Typer(name="siftguard", help="Autonomous DFIR agent for SANS SIFT Workstation.")
console = Console()


@app.command()
def investigate(
    case_id: str = typer.Argument(..., help="Unique case identifier, e.g. CASE-2026-001"),
    briefing: str = typer.Option(..., "--briefing", "-b", help="Short description of the incident"),
    memory: str = typer.Option("", "--memory", "-m", help="Path to memory image"),
    disk: str = typer.Option("", "--disk", "-d", help="Path to disk image"),
    mft: str = typer.Option("", "--mft", help="Path to extracted $MFT"),
    audit_db: str = typer.Option("./audit/siftguard.db", "--audit-db"),
) -> None:
    """Run SIFTGuard autonomous investigation on a case."""
    from siftguard.agent.loop import run_case

    evidence: dict[str, str] = {}
    if memory:
        evidence["memory_image"] = memory
    if disk:
        evidence["disk_image"] = disk
    if mft:
        evidence["mft"] = mft

    if not evidence:
        console.print(
            "[red]Error:[/red] Provide at least one evidence file (--memory, --disk, or --mft)"
        )
        raise typer.Exit(1)

    report = asyncio.run(
        run_case(
            case_id=case_id,
            evidence_files=evidence,
            briefing=briefing,
            audit_db=audit_db,
        )
    )

    output_path = Path(f"./audit/{case_id}_report.md")
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(report)
    console.print(f"\n[bold]Report saved:[/bold] {output_path}")


@app.command()
def server() -> None:
    """Start SIFTGuard MCP server (stdio transport)."""
    from siftguard.mcp_server.server import main

    main()


if __name__ == "__main__":
    app()
