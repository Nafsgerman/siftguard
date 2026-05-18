"""SIFTGuard agent loop — v1 (baseline, frozen behaviour).

This is the original loop.py code extracted verbatim.
DO NOT modify this file. It is the v1.0.0 baseline for ablation comparisons.
Any behavioural changes belong in loop_v2.py.

ADR: docs/adr/ADR-003-loop-instrumentation.md
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv()

from siftguard.agent.prompts import load_prompt
from siftguard.audit.log import AuditLog
from siftguard.mcp_server.tools.filesystem import extract_file, list_files
from siftguard.mcp_server.tools.mft import analyze_mft
from siftguard.mcp_server.tools.registry import run_regripper
from siftguard.mcp_server.tools.timeline import create_supertimeline, sort_timeline
from siftguard.mcp_server.tools.volatility import vol_malfind, vol_netscan, vol_pslist
from siftguard.models.forensic import ForensicResult

console = Console()

MAX_ITERATIONS = int(os.environ.get("SIFTGUARD_MAX_AGENT_ITERATIONS", "15"))

TOOL_REGISTRY = {
    "analyze_mft": lambda **a: analyze_mft(
        **{**a, "memory_image": a.get("memory_image") or a.get("mft_path", "")}
    ),
    "vol_pslist": vol_pslist,
    "vol_netscan": vol_netscan,
    "vol_malfind": vol_malfind,
    "create_supertimeline": create_supertimeline,
    "sort_timeline": sort_timeline,
    "run_regripper": run_regripper,
    "list_files": list_files,
    "extract_file": extract_file,
}

TOOL_SCHEMAS = [
    {
        "name": "analyze_mft",
        "description": "Parse Windows $MFT entries directly from a memory image via Volatility3. READ-ONLY.",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_image": {"type": "string"},
                "timestomp_only": {"type": "boolean", "default": False},
            },
            "required": ["memory_image"],
        },
    },
    {
        "name": "vol_pslist",
        "description": "List processes from memory image. Flags suspicious names/parent-child combos. READ-ONLY.",
        "input_schema": {
            "type": "object",
            "properties": {"memory_image": {"type": "string"}},
            "required": ["memory_image"],
        },
    },
    {
        "name": "vol_netscan",
        "description": "Scan memory image for network connections. READ-ONLY.",
        "input_schema": {
            "type": "object",
            "properties": {"memory_image": {"type": "string"}},
            "required": ["memory_image"],
        },
    },
    {
        "name": "vol_malfind",
        "description": "Find injected code and suspicious memory regions. READ-ONLY.",
        "input_schema": {
            "type": "object",
            "properties": {"memory_image": {"type": "string"}},
            "required": ["memory_image"],
        },
    },
    {
        "name": "create_supertimeline",
        "description": "Run log2timeline to build a plaso supertimeline. READ-ONLY.",
        "input_schema": {
            "type": "object",
            "properties": {
                "evidence_path": {"type": "string"},
                "output_plaso": {"type": "string", "default": "/tmp/siftguard_timeline.plaso"},
            },
            "required": ["evidence_path"],
        },
    },
    {
        "name": "sort_timeline",
        "description": "Run psort to produce sorted CSV timeline from plaso file. READ-ONLY.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plaso_file": {"type": "string"},
                "output_csv": {"type": "string", "default": "/tmp/siftguard_sorted.csv"},
                "filter_date_start": {"type": "string"},
            },
            "required": ["plaso_file"],
        },
    },
    {
        "name": "run_regripper",
        "description": "Run regripper plugin against registry hive. Plugins: autoruns,services,run,userassist,shellbags,recentdocs,networklist,timezone,samparse. READ-ONLY.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hive_path": {"type": "string"},
                "plugin": {"type": "string", "default": "autoruns"},
            },
            "required": ["hive_path"],
        },
    },
    {
        "name": "list_files",
        "description": "List files in disk image using fls. Recovers deleted files. READ-ONLY.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string"},
                "offset": {"type": "string", "default": ""},
                "recursive": {"type": "boolean", "default": True},
            },
            "required": ["image_path"],
        },
    },
    {
        "name": "extract_file",
        "description": "Extract file from disk image by inode using icat. READ-ONLY.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string"},
                "inode": {"type": "string"},
                "output_path": {"type": "string"},
                "offset": {"type": "string", "default": ""},
            },
            "required": ["image_path", "inode", "output_path"],
        },
    },
]


class HypothesisStatus(str, Enum):
    FORMING = "forming"
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"


@dataclass
class Hypothesis:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    statement: str = ""
    status: HypothesisStatus = HypothesisStatus.FORMING
    supporting_evidence: list[str] = field(default_factory=list)
    refuting_evidence: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class CaseContext:
    case_id: str
    evidence_files: dict[str, str]
    briefing: str
    hypotheses: list[Hypothesis] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    iteration: int = 0


async def _dispatch_tool(name: str, args: dict) -> ForensicResult:
    fn = TOOL_REGISTRY.get(name)
    if not fn:
        from siftguard.models.forensic import ToolOutcome

        return ForensicResult(
            tool=name,
            outcome=ToolOutcome.FAIL,
            summary=f"unknown tool: {name}",
            duration_ms=0,
            error="tool not found in registry",
        )
    return await fn(**args)


async def run_case_v1(
    case_id: str,
    evidence_files: dict[str, str],
    briefing: str,
    audit_db: str = "./audit/siftguard.db",
    training_mode: bool = False,
) -> str:
    """
    v1 agent loop. Frozen behaviour — do not modify.
    Returns the final incident report as a string.
    """
    audit = AuditLog(audit_db)
    ctx = CaseContext(
        case_id=case_id,
        evidence_files=evidence_files,
        briefing=briefing,
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt_version = "v1_training" if training_mode else "v1"
    system_prompt = load_prompt(prompt_version)

    evidence_summary = "\n".join(f"- {label}: {path}" for label, path in evidence_files.items())
    initial_message = (
        f"## Case ID: {case_id}\n\n"
        f"## Briefing\n{briefing}\n\n"
        f"## Available Evidence\n{evidence_summary}\n\n"
        "Begin your investigation. Form an initial hypothesis and start collecting evidence."
    )

    messages: list[dict] = [{"role": "user", "content": initial_message}]

    console.print(
        Panel(
            f"[bold cyan]SIFTGuard v1[/bold cyan] — Case [yellow]{case_id}[/yellow]\n{briefing[:200]}",
            title="Investigation Started",
            border_style="cyan",
        )
    )

    final_report = ""

    for iteration in range(MAX_ITERATIONS):
        ctx.iteration = iteration
        console.print(f"\n[dim]── Iteration {iteration + 1}/{MAX_ITERATIONS} ──[/dim]")

        response = client.messages.create(
            model=os.environ.get("SIFTGUARD_MODEL", "claude-sonnet-4-6"),
            max_tokens=4096,
            system=system_prompt,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        assistant_content = []
        tool_calls_made = []

        for block in response.content:
            assistant_content.append(block)
            if block.type == "text":
                if block.text.strip():
                    console.print(f"[green]Agent:[/green] {block.text[:500]}")
                if "## Executive Summary" in block.text:
                    final_report = block.text
            elif block.type == "tool_use":
                tool_calls_made.append(block)
                console.print(
                    f"[yellow]→ Tool:[/yellow] [bold]{block.name}[/bold] "
                    f"{json.dumps(block.input)[:100]}"
                )

        messages.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason == "end_turn" and not tool_calls_made:
            if final_report:
                break
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Please now compile your final incident report using the required headers: "
                        "## Executive Summary, ## Timeline of Events, ## Indicators of Compromise, "
                        "## Persistence Mechanisms, ## Recommendations, ## Evidence References"
                    ),
                }
            )
            continue

        if tool_calls_made:
            tool_results = []
            for tool_call in tool_calls_made:
                result = await _dispatch_tool(tool_call.name, tool_call.input)

                audit.record(
                    case_id=case_id,
                    tool_name=tool_call.name,
                    tool_version="1.0.0",
                    args=tool_call.input,
                    outcome=result.outcome.value,
                    output=result.model_dump_json(),
                    duration_ms=result.duration_ms,
                    agent_iteration=iteration,
                )

                result_text = result.model_dump_json(indent=2)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": result_text[:8000],
                    }
                )

                ctx.findings.append(f"[iter{iteration}] {tool_call.name}: {result.summary}")
                _print_result_summary(tool_call.name, result)

            messages.append({"role": "user", "content": tool_results})

    if not final_report:
        final_report = "Investigation incomplete — max iterations reached without final report."

    _print_final_report(case_id, ctx, final_report, audit)
    return final_report


def _print_result_summary(tool_name: str, result: ForensicResult) -> None:
    color = "green" if result.outcome.value == "ok" else "red"
    console.print(f"  [{color}]✓ {tool_name}:[/{color}] {result.summary} ({result.duration_ms}ms)")


def _print_final_report(case_id: str, ctx: CaseContext, report: str, audit: AuditLog) -> None:
    entries = audit.for_case(case_id)
    table = Table(title=f"Audit Trail — {case_id}", show_lines=True)
    table.add_column("Iter", style="dim", width=4)
    table.add_column("Tool", style="cyan")
    table.add_column("Outcome", style="green")
    table.add_column("Duration")
    for e in entries[-20:]:
        table.add_row(
            str(e.agent_iteration),
            e.tool_name,
            e.outcome,
            f"{e.duration_ms}ms",
        )
    console.print(table)
    console.print(
        Panel(
            report,
            title="[bold green]Incident Report[/bold green]",
            border_style="green",
        )
    )
