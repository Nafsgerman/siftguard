"""OpenAI function-calling orchestrator adapter for SIFTGuard.

Single-variable claim: orchestration changes, model/tools/scorer unchanged.
Uses the same _dispatch_tool, same TOOL_SCHEMAS, same scorer as the native
and LangGraph adapters — only the orchestration paradigm differs.

Orchestration: imperative while-loop (no graph-DAG).
Client: OpenAI Python SDK, model gpt-4o, tool_choice="auto".
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

try:
    import openai
except ImportError as _e:
    raise ImportError("pip install openai") from _e

from siftguard.agent.instrumentation import SnapshotWriter, token_cost
from siftguard.agent.loop_v2 import (
    DEFAULT_MODEL,
    IOC_TYPES,
    MAX_ITERATIONS,
    TOOL_SCHEMAS,
    _dispatch_tool,
    _synthesize_v1_fallback,
)
from siftguard.agent.output_schema import AgentOutput, NextAction
from siftguard.agent.output_validator import is_v2_response, parse_agent_output
from siftguard.agent.prompts import load_prompt
from siftguard.audit.log import AuditLog

logger = logging.getLogger(__name__)

# ── Tool schema conversion ────────────────────────────────────────────────────
# Anthropic: {name, description, input_schema: {type, properties, required}}
# OpenAI:    {type: "function", function: {name, description, parameters: {type, properties, required}}}

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in TOOL_SCHEMAS
]

# ── Public entry point ────────────────────────────────────────────────────────

async def run_case_openai_fc(
    case_id: str,
    evidence_files: dict[str, str],
    briefing: str,
    audit_db: str = "./audit/siftguard.db",
    training_mode: bool = False,
    model: str = "gpt-5.5",
    config_override: Optional[dict] = None,
    ground_truth_path: Optional[str] = None,
    on_event: Optional[callable] = None,
) -> tuple[str, str]:
    """OpenAI FC-orchestrated investigation. Returns (report, run_id).

    Imperative while-loop — no StateGraph. Same _dispatch_tool, same
    TOOL_SCHEMAS, same scorer as native and LangGraph adapters.
    """
    run_id = str(uuid.uuid4())
    seed = (config_override or {}).get("seed", 0)
    max_iter = (config_override or {}).get("max_iterations", MAX_ITERATIONS)
    prompt_version = "v2_training" if training_mode else "v2"
    system_prompt = load_prompt(prompt_version)

    config = {
        "agent_id": "siftguard-openai-fc",
        "model": model,
        "orchestrator": "openai-fc",
        "self_correction": True,
        "correlation": True,
        "training_mode": training_mode,
        "max_iterations": max_iter,
        "prompt_version": prompt_version,
        **(config_override or {}),
    }

    snap = SnapshotWriter(audit_db)
    snap.write_experiment_run_start(
        run_id=run_id,
        case_id=case_id,
        agent_id="siftguard-openai-fc",
        config=config,
        ground_truth_path=ground_truth_path,
    )

    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

    evidence_summary = "\n".join(f"- {k}: {v}" for k, v in evidence_files.items())
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"## Case ID: {case_id}\n\n"
                f"## Briefing\n{briefing}\n\n"
                f"## Available Evidence\n{evidence_summary}\n\n"
                "Begin your investigation. Form an initial hypothesis. "
                "Remember to end every response with the required JSON block."
            ),
        },
    ]

    if on_event:
        on_event("investigation_started", {
            "run_id": run_id, "case_id": case_id,
            "model": model, "orchestrator": "openai-fc",
        })

    all_findings: list[dict] = []
    all_hypotheses: list[dict] = []
    cumulative_tokens_in = 0
    cumulative_tokens_out = 0
    cumulative_cost_usd = 0.0
    final_report = ""
    terminated_reason = "max_iterations"
    iter_count = 0

    while iter_count < max_iter:
        # ── API call ──────────────────────────────────────────────────────────
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=OPENAI_TOOLS,
            tool_choice="auto",
            seed=seed,
            temperature=0,
        )

        tokens_in = response.usage.prompt_tokens
        tokens_out = response.usage.completion_tokens
        cost = token_cost(model, tokens_in, tokens_out)

        cumulative_tokens_in += tokens_in
        cumulative_tokens_out += tokens_out
        cumulative_cost_usd += cost
        iter_count += 1

        if on_event:
            on_event("token_usage", {
                "iteration": iter_count,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": cost,
                "cumulative_cost_usd": cumulative_cost_usd,
            })

        msg = response.choices[0].message
        tool_calls = msg.tool_calls or []
        text = msg.content or ""

        # ── Check for final report ────────────────────────────────────────────
        if "## Executive Summary" in text and len(text) > 1500:
            final_report = text
            terminated_reason = "verdict_reached"
            break

        # ── Append assistant turn to history ──────────────────────────────────
        assistant_entry: dict = {"role": "assistant", "content": text}
        if tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ]
        messages.append(assistant_entry)

        # ── Tool dispatch ─────────────────────────────────────────────────────
        if tool_calls:
            audit = AuditLog(audit_db)
            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                if on_event:
                    on_event("tool_call_start", {
                        "tool": tc.function.name,
                        "iteration": iter_count,
                        "args": args,
                    })

                result = await _dispatch_tool(tc.function.name, args)

                audit.record(
                    case_id=case_id,
                    tool_name=tc.function.name,
                    tool_version="2.0.0",
                    args=args,
                    outcome=result.outcome.value,
                    output=result.model_dump_json(),
                    duration_ms=result.duration_ms,
                    agent_iteration=iter_count,
                    run_id=run_id,
                    tokens_in=cumulative_tokens_in,
                    tokens_out=cumulative_tokens_out,
                    cost_usd=0.0,
                    correction_event=None,
                )

                if on_event:
                    on_event("tool_call_end", {
                        "tool": tc.function.name,
                        "outcome": result.outcome.value,
                        "summary": result.summary,
                        "duration_ms": result.duration_ms,
                        "iteration": iter_count,
                    })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result.model_dump_json(indent=2)[:8000],
                })

        # ── Parse v2 structured output (synthesis turns only) ─────────────────
        agent_out: Optional[AgentOutput] = None
        if not tool_calls and is_v2_response(text):
            agent_out, _ = parse_agent_output(text)
            if agent_out is None:
                agent_out = _synthesize_v1_fallback(text, iter_count)
        elif tool_calls:
            agent_out = AgentOutput(
                iteration_summary=f"Tool calls: {[tc.function.name for tc in tool_calls]}",
                findings=[],
                hypotheses=[],
                next_action=NextAction(decision="continue", tool_to_call=None, rationale="tool turn"),
                verdict=None,
            )
        else:
            agent_out = _synthesize_v1_fallback(text, iter_count)

        # ── Update findings ───────────────────────────────────────────────────
        seen_keys = {(f["type"], f["value"].lower()) for f in all_findings}
        for f in (agent_out.findings if agent_out else []):
            key = (f.type, f.value.lower())
            if key not in seen_keys:
                all_findings.append(f.model_dump())
                seen_keys.add(key)
                if f.type in IOC_TYPES and on_event:
                    on_event("ioc_detected", {
                        "type": f.type, "value": f.value,
                        "confidence": f.confidence,
                        "iteration": iter_count,
                    })

        all_hypotheses = [h.model_dump() for h in (agent_out.hypotheses if agent_out else [])]

        # ── Snapshot ──────────────────────────────────────────────────────────
        iocs = [f for f in all_findings if f.get("type") in IOC_TYPES]
        snap.write_iteration_snapshot(
            run_id=run_id,
            case_id=case_id,
            iteration=iter_count,
            findings=all_findings,
            iocs=iocs,
            hypotheses=all_hypotheses,
            cumulative_tokens_in=cumulative_tokens_in,
            cumulative_tokens_out=cumulative_tokens_out,
            cumulative_cost_usd=cumulative_cost_usd,
            wall_time_ms=0,
        )

        if on_event:
            on_event("iteration_complete", {
                "iteration": iter_count,
                "findings_count": len(all_findings),
                "iocs_count": len(iocs),
                "cumulative_cost_usd": cumulative_cost_usd,
            })

        # ── Verdict / abort checks ─────────────────────────────────────────────
        if agent_out and agent_out.next_action.decision == "verdict":
            terminated_reason = "verdict_reached"
            if on_event:
                on_event("verdict_reached", {
                    "run_id": run_id,
                    "claim": agent_out.verdict.claim if agent_out.verdict else "",
                    "confidence": agent_out.verdict.confidence if agent_out.verdict else None,
                    "findings_count": len(all_findings),
                    "total_cost_usd": cumulative_cost_usd,
                })
            break

        if agent_out and agent_out.next_action.decision == "abort":
            terminated_reason = "aborted"
            break

        # ── End-turn nudge (no tool calls, no verdict) ────────────────────────
        if not tool_calls and response.choices[0].finish_reason == "stop":
            if final_report:
                terminated_reason = "verdict_reached"
                break
            messages.append({
                "role": "user",
                "content": (
                    "Please compile your final incident report using the required headers, "
                    "then append the JSON block with decision='verdict'."
                ),
            })

    # ── Finalise ──────────────────────────────────────────────────────────────
    if not final_report:
        final_report = (
            f"Investigation incomplete — {terminated_reason} after {iter_count} iterations."
        )

    snap.write_experiment_run_complete(
        run_id=run_id,
        completed_iterations=iter_count,
        terminated_reason=terminated_reason,
        total_tokens_in=cumulative_tokens_in,
        total_tokens_out=cumulative_tokens_out,
        total_cost_usd=cumulative_cost_usd,
    )

    return final_report, run_id
