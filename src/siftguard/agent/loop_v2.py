"""SIFTGuard agent loop — v2 (instrumented, structured-confidence output).

Key differences from v1:
- Uses v2 structured-JSON prompt (or v2_training in training mode)
- Parses AgentOutput Pydantic schema from every response
- Single retry on schema failure; v1-style fallback on second failure
- Real iteration counters, token/cost capture, hypothesis events,
  iteration snapshots, and experiment_run records
- run_id links all audit rows to a single experiment run

ADR: docs/adr/ADR-004-loop-instrumentation.md
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv()

from siftguard.agent.instrumentation import (
    HypothesisTracker,
    SnapshotWriter,
    token_cost,
)
from siftguard.agent.output_schema import AgentOutput, FindingOutput
from siftguard.agent.output_validator import (
    build_retry_message,
    is_v2_response,
    parse_agent_output,
)
from siftguard.agent.prompts import load_prompt
from siftguard.audit.log import AuditLog
from siftguard.mcp_server.tools.mft import analyze_mft
from siftguard.mcp_server.tools.volatility import vol_pslist, vol_netscan, vol_malfind
from siftguard.mcp_server.tools.timeline import create_supertimeline, sort_timeline
from siftguard.mcp_server.tools.registry import run_regripper
from siftguard.mcp_server.tools.filesystem import list_files, extract_file
from siftguard.models.forensic import ForensicResult, ToolOutcome

logger = logging.getLogger(__name__)
console = Console()

MAX_ITERATIONS = int(os.environ.get("SIFTGUARD_MAX_AGENT_ITERATIONS", "15"))
DEFAULT_MODEL   = os.environ.get("SIFTGUARD_MODEL", "claude-sonnet-4-20250514")

IOC_TYPES = {"process", "ip", "port", "technique"}

TOOL_REGISTRY = {
    "analyze_mft": lambda **a: analyze_mft(**{**a, "memory_image": a.get("memory_image") or a.get("mft_path", "")}),
    "vol_pslist":         vol_pslist,
    "vol_netscan":        vol_netscan,
    "vol_malfind":        vol_malfind,
    "create_supertimeline": create_supertimeline,
    "sort_timeline":      sort_timeline,
    "run_regripper":      run_regripper,
    "list_files":         list_files,
    "extract_file":       extract_file,
}

TOOL_SCHEMAS = [
    {"name": "analyze_mft", "description": "Parse Windows $MFT entries directly from a memory image via Volatility3. READ-ONLY.", "input_schema": {"type": "object", "properties": {"memory_image": {"type": "string"}, "timestomp_only": {"type": "boolean", "default": False}}, "required": ["memory_image"]}},
    {"name": "vol_pslist", "description": "List processes from memory image. Flags suspicious names/parent-child combos. READ-ONLY.", "input_schema": {"type": "object", "properties": {"memory_image": {"type": "string"}}, "required": ["memory_image"]}},
    {"name": "vol_netscan", "description": "Scan memory image for network connections. READ-ONLY.", "input_schema": {"type": "object", "properties": {"memory_image": {"type": "string"}}, "required": ["memory_image"]}},
    {"name": "vol_malfind", "description": "Find injected code and suspicious memory regions. READ-ONLY.", "input_schema": {"type": "object", "properties": {"memory_image": {"type": "string"}}, "required": ["memory_image"]}},
    {"name": "create_supertimeline", "description": "Run log2timeline to build a plaso supertimeline. READ-ONLY.", "input_schema": {"type": "object", "properties": {"evidence_path": {"type": "string"}, "output_plaso": {"type": "string", "default": "/tmp/siftguard_timeline.plaso"}}, "required": ["evidence_path"]}},
    {"name": "sort_timeline", "description": "Run psort to produce sorted CSV timeline from plaso file. READ-ONLY.", "input_schema": {"type": "object", "properties": {"plaso_file": {"type": "string"}, "output_csv": {"type": "string", "default": "/tmp/siftguard_sorted.csv"}, "filter_date_start": {"type": "string"}}, "required": ["plaso_file"]}},
    {"name": "run_regripper", "description": "Run regripper plugin against registry hive. Plugins: autoruns,services,run,userassist,shellbags,recentdocs,networklist,timezone,samparse. READ-ONLY.", "input_schema": {"type": "object", "properties": {"hive_path": {"type": "string"}, "plugin": {"type": "string", "default": "autoruns"}}, "required": ["hive_path"]}},
    {"name": "list_files", "description": "List files in disk image using fls. Recovers deleted files. READ-ONLY.", "input_schema": {"type": "object", "properties": {"image_path": {"type": "string"}, "offset": {"type": "string", "default": ""}, "recursive": {"type": "boolean", "default": True}}, "required": ["image_path"]}},
    {"name": "extract_file", "description": "Extract file from disk image by inode using icat. READ-ONLY.", "input_schema": {"type": "object", "properties": {"image_path": {"type": "string"}, "inode": {"type": "string"}, "output_path": {"type": "string"}, "offset": {"type": "string", "default": ""}}, "required": ["image_path", "inode", "output_path"]}},
]


@dataclass
class V2RunState:
    """Mutable state accumulated across iterations."""
    run_id: str
    case_id: str
    model: str
    cumulative_tokens_in:  int   = 0
    cumulative_tokens_out: int   = 0
    cumulative_cost_usd:   float = 0.0
    all_findings:  list[dict] = field(default_factory=list)
    all_hypotheses: list[dict] = field(default_factory=list)
    run_start_ms:  float = field(default_factory=time.time)
    terminated_reason: str = "max_iterations"
    completed_iterations: int = 0


async def _dispatch_tool(name: str, args: dict) -> ForensicResult:
    fn = TOOL_REGISTRY.get(name)
    if not fn:
        return ForensicResult(
            tool=name, outcome=ToolOutcome.FAIL,
            summary=f"unknown tool: {name}", duration_ms=0,
            error="tool not found in registry",
        )
    return await fn(**args)


def _extract_text_blocks(content: list) -> str:
    return "\n".join(
        block.text for block in content
        if hasattr(block, "type") and block.type == "text"
    )


def _synthesize_v1_fallback(response_text: str, iteration: int) -> AgentOutput:
    """
    Build a minimal AgentOutput from free-form v1 text.
    confidence=None on all findings — calibration panel excludes this run honestly.
    """
    from siftguard.agent.output_schema import NextAction
    logger.warning(
        "v2 schema parse failed twice at iteration %d — using v1 fallback synthesis",
        iteration,
    )
    return AgentOutput(
        iteration_summary=response_text[:200] + "... [v1-fallback]",
        findings=[],
        hypotheses=[],
        next_action=NextAction(
            decision="continue",
            tool_to_call=None,
            rationale="v1 fallback — schema parse failed",
        ),
        verdict=None,
    )


async def run_case_v2(
    case_id: str,
    evidence_files: dict[str, str],
    briefing: str,
    audit_db: str = "./audit/siftguard.db",
    training_mode: bool = False,
    model: str = DEFAULT_MODEL,
    max_iterations: Optional[int] = None,
    config_override: Optional[dict] = None,
    ground_truth_path: Optional[str] = None,
    on_event: Optional[callable] = None,
) -> tuple[str, str]:
    """
    v2 instrumented agent loop.

    Returns:
        (final_report: str, run_id: str)

    on_event: optional callback for SSE streaming.
        Called with (event_type: str, data: dict).
        Dashboard wires this to its SSE emitter.
    """
    run_id  = str(uuid.uuid4())
    audit   = AuditLog(audit_db)
    snap    = SnapshotWriter(audit_db)
    tracker = HypothesisTracker()
    client  = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt_version = "v2_training" if training_mode else "v2"
    system_prompt  = load_prompt(prompt_version)
    _max_iter = max_iterations or MAX_ITERATIONS

    config = {
        "agent_id":        "siftguard-v2",
        "model":           model,
        "orchestrator":    "siftguard-native",
        "self_correction": True,
        "correlation":     True,
        "training_mode":   training_mode,
        "max_iterations":  _max_iter,
        "prompt_version":  prompt_version,
        **(config_override or {}),
    }

    snap.write_experiment_run_start(
        run_id=run_id,
        case_id=case_id,
        agent_id="siftguard-v2",
        config=config,
        ground_truth_path=ground_truth_path,
    )

    state = V2RunState(run_id=run_id, case_id=case_id, model=model)

    evidence_summary = "\n".join(
        f"- {label}: {path}" for label, path in evidence_files.items()
    )
    initial_message = (
        f"## Case ID: {case_id}\n\n"
        f"## Briefing\n{briefing}\n\n"
        f"## Available Evidence\n{evidence_summary}\n\n"
        "Begin your investigation. Form an initial hypothesis. "
        "Remember to end every response with the required JSON block."
    )

    messages: list[dict] = [{"role": "user", "content": initial_message}]

    console.print(Panel(
        f"[bold cyan]SIFTGuard v2[/bold cyan] — Case [yellow]{case_id}[/yellow]\n"
        f"[dim]run_id: {run_id}[/dim]\n{briefing[:200]}",
        title="Investigation Started", border_style="cyan",
    ))

    if on_event:
        on_event("investigation_started", {
            "run_id": run_id, "case_id": case_id, "model": model,
        })

    final_report = ""
    iter_wall_start = time.time()

    for iteration in range(_max_iter):
        state.completed_iterations = iteration + 1
        console.print(f"\n[dim]── Iteration {iteration + 1}/{_max_iter} ──[/dim]")

        # Edit 1: line 233 (in main client.messages.create call)
        response = client.messages.create(
            model=model,
            max_tokens=8192,           # was 4096
            system=system_prompt,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        tokens_in  = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        cost       = token_cost(model, tokens_in, tokens_out)

        state.cumulative_tokens_in  += tokens_in
        state.cumulative_tokens_out += tokens_out
        state.cumulative_cost_usd   += cost

        if on_event:
            on_event("token_usage", {
                "iteration": iteration,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": cost,
                "cumulative_cost_usd": state.cumulative_cost_usd,
            })

        # ── Collect content ─────────────────────────────────────────────────
        assistant_content = []
        tool_calls_made   = []
        response_text     = ""

        for block in response.content:
            assistant_content.append(block)
            if block.type == "text":
                response_text += block.text
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

        # ── Early exit: substantial report written, even if response truncated ──
        if final_report and "## Executive Summary" in final_report and len(final_report) > 1500:
            if on_event:
                on_event("verdict_reached", {
                    "run_id": run_id,
                    "claim": "Investigation complete (report-based exit)",
                    "confidence": None,
                    "findings_count": len(state.all_findings),
                    "total_cost_usd": state.cumulative_cost_usd,
                })
            state.terminated_reason = "verdict_reached"
            break

       # ── Parse v2 structured output ──────────────────────────────────────
        # Only parse v2 JSON on synthesis turns (no tool calls).
        # On tool-calling turns the structured output IS the tool_use block —
        # no JSON block is expected and attempting to parse one causes false
        # v1-fallback on every tool-calling iteration.
        agent_out: Optional[AgentOutput] = None
        if not tool_calls_made and is_v2_response(response_text):
            agent_out, error = parse_agent_output(response_text)
            if agent_out is None:
                # Single retry
                logger.warning("v2 parse failed iter %d — retrying: %s", iteration, error)
                retry_msg = build_retry_message(error)
                messages.append({"role": "user", "content": retry_msg})
                # Edit 2: line 290 (in retry client.messages.create call)
                retry_resp = client.messages.create(
                    model=model, max_tokens=8192,        # was 4096
                    system=system_prompt, tools=TOOL_SCHEMAS, messages=messages,
                )
                retry_text = _extract_text_blocks(retry_resp.content)
                agent_out, error2 = parse_agent_output(retry_text)
                if agent_out is None:
                    agent_out = _synthesize_v1_fallback(response_text, iteration)
                else:
                    messages.append({
                        "role": "assistant",
                        "content": retry_resp.content,
                    })
        elif tool_calls_made:
            # Tool-calling turn — build minimal AgentOutput from tool calls.
            # v2 JSON verdict appears only on the final synthesis turn.
            from siftguard.agent.output_schema import NextAction
            agent_out = AgentOutput(
                iteration_summary=f"Tool calls: {[t.name for t in tool_calls_made]}",
                findings=[],
                hypotheses=[],
                next_action=NextAction(
                    decision="continue",
                    tool_to_call=None,
                    rationale="Tool-calling turn — continuing investigation.",
                ),
                verdict=None,
            )
        else:
            agent_out = _synthesize_v1_fallback(response_text, iteration)

        # ── Hypothesis events ────────────────────────────────────────────────
        hyp_dicts = [h.model_dump() for h in agent_out.hypotheses]
        hyp_events = tracker.diff(hyp_dicts)
        snap.write_hypothesis_events(run_id, case_id, iteration, hyp_events)

        if on_event and hyp_events:
            on_event("hypothesis_update", {
                "iteration": iteration,
                "events": hyp_events,
            })

        # ── Update cumulative findings ───────────────────────────────────────
        seen_keys: set[tuple] = {
            (f["type"], f["value"].lower())
            for f in state.all_findings
        }
        for f in agent_out.findings:
            key = (f.type, f.value.lower())
            if key not in seen_keys:
                state.all_findings.append(f.model_dump())
                seen_keys.add(key)
                if f.type in IOC_TYPES and on_event:
                    on_event("ioc_detected", {
                        "type": f.type,
                        "value": f.value,
                        "confidence": f.confidence,
                        "mitre_technique": f.mitre_technique,
                        "iteration": iteration,
                    })

        state.all_hypotheses = hyp_dicts

        # ── End-of-iteration snapshot ────────────────────────────────────────
        iocs = [f for f in state.all_findings if f.get("type") in IOC_TYPES]
        snap.write_iteration_snapshot(
            run_id=run_id,
            case_id=case_id,
            iteration=iteration,
            findings=state.all_findings,
            iocs=iocs,
            hypotheses=state.all_hypotheses,
            cumulative_tokens_in=state.cumulative_tokens_in,
            cumulative_tokens_out=state.cumulative_tokens_out,
            cumulative_cost_usd=state.cumulative_cost_usd,
            wall_time_ms=int((time.time() - iter_wall_start) * 1000),
        )

        if on_event:
            on_event("iteration_complete", {
                "iteration": iteration,
                "findings_count": len(state.all_findings),
                "iocs_count": len(iocs),
                "cumulative_cost_usd": state.cumulative_cost_usd,
            })

        # ── Tool calls ───────────────────────────────────────────────────────
        if response.stop_reason == "end_turn" and not tool_calls_made:
            if final_report:
                state.terminated_reason = "verdict_reached"
                break
            messages.append({
                "role": "user",
                "content": (
                    "Please compile your final incident report using the required headers, "
                    "then append the JSON block with decision='verdict'."
                ),
            })
            continue

        if tool_calls_made:
            tool_results = []
            for tool_call in tool_calls_made:
                if on_event:
                    on_event("tool_call_start", {
                        "tool": tool_call.name,
                        "iteration": iteration,
                        "args": tool_call.input,
                    })

                result = await _dispatch_tool(tool_call.name, tool_call.input)

                # Audit row with all new columns populated
                audit.record(
                    case_id=case_id,
                    tool_name=tool_call.name,
                    tool_version="2.0.0",
                    args=tool_call.input,
                    outcome=result.outcome.value,
                    output=result.model_dump_json(),
                    duration_ms=result.duration_ms,
                    agent_iteration=iteration,          # real counter
                    run_id=run_id,                      # NEW
                    tokens_in=tokens_in,                # NEW
                    tokens_out=tokens_out,              # NEW
                    cost_usd=cost,                      # NEW
                    correction_event=(
                        agent_out.correction_event
                        if agent_out else None
                    ),                                  # NEW
                )

                if on_event:
                    on_event("tool_call_end", {
                        "tool": tool_call.name,
                        "outcome": result.outcome.value,
                        "summary": result.summary,
                        "duration_ms": result.duration_ms,
                        "iteration": iteration,
                    })

                _print_result_summary(tool_call.name, result)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": result.model_dump_json(indent=2)[:8000],
                })

            messages.append({"role": "user", "content": tool_results})

        # ── Verdict check ────────────────────────────────────────────────────
        if agent_out and agent_out.next_action.decision == "verdict":
            state.terminated_reason = "verdict_reached"
            if on_event:
                on_event("verdict_reached", {
                    "run_id": run_id,
                    "claim": agent_out.verdict.claim if agent_out.verdict else "",
                    "confidence": agent_out.verdict.confidence if agent_out.verdict else None,
                    "findings_count": len(state.all_findings),
                    "total_cost_usd": state.cumulative_cost_usd,
                })
            break

        if agent_out and agent_out.next_action.decision == "abort":
            state.terminated_reason = "aborted"
            break

    # ── Finalise ─────────────────────────────────────────────────────────────
    if not final_report:
        final_report = (
            "Investigation incomplete — "
            f"{state.terminated_reason} after {state.completed_iterations} iterations."
        )

    snap.write_experiment_run_complete(
        run_id=run_id,
        completed_iterations=state.completed_iterations,
        terminated_reason=state.terminated_reason,
        total_tokens_in=state.cumulative_tokens_in,
        total_tokens_out=state.cumulative_tokens_out,
        total_cost_usd=state.cumulative_cost_usd,
    )

    _print_final_report_v2(case_id, run_id, state, final_report, audit)
    return final_report, run_id


def _print_result_summary(tool_name: str, result: ForensicResult) -> None:
    color = "green" if result.outcome.value == "ok" else "red"
    console.print(
        f"  [{color}]✓ {tool_name}:[/{color}] "
        f"{result.summary} ({result.duration_ms}ms)"
    )


def _print_final_report_v2(
    case_id: str,
    run_id: str,
    state: V2RunState,
    report: str,
    audit: AuditLog,
) -> None:
    entries = audit.for_case(case_id)
    table = Table(
        title=f"Audit Trail — {case_id} [dim](run {run_id[:8]})[/dim]",
        show_lines=True,
    )
    table.add_column("Iter",   style="dim", width=4)
    table.add_column("Tool",   style="cyan")
    table.add_column("Outcome", style="green")
    table.add_column("ms")
    table.add_column("Tokens")
    table.add_column("Cost $")
    for e in entries[-20:]:
        table.add_row(
            str(e.agent_iteration),
            e.tool_name,
            e.outcome,
            str(e.duration_ms),
            str((e.tokens_in or 0) + (e.tokens_out or 0)),
            f"{e.cost_usd:.6f}" if e.cost_usd else "—",
        )
    console.print(table)
    console.print(
        f"\n[dim]Total cost: ${state.cumulative_cost_usd:.4f} | "
        f"Tokens in: {state.cumulative_tokens_in:,} | "
        f"Tokens out: {state.cumulative_tokens_out:,}[/dim]"
    )
    console.print(Panel(
        report,
        title="[bold green]Incident Report[/bold green]",
        border_style="green",
    ))