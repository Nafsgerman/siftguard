"""LangGraph orchestrator adapter for SIFTGuard.

Single-variable claim: orchestration changes, model/tools/scorer unchanged.

State machine:
  START → think_node → tool_router → tool_node → observe_node → think_node (loop)
                                  ↓
                                 END
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Optional, TypedDict

import anthropic
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph


load_dotenv()

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


# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: list
    iter_count: int
    max_iter: int
    run_id: str
    case_id: str
    model: str
    system_prompt: str
    seed: int
    all_findings: list[dict]
    all_hypotheses: list[dict]
    cumulative_tokens_in: int
    cumulative_tokens_out: int
    cumulative_cost_usd: float
    final_report: str
    terminated_reason: str
    audit_db: str
    ground_truth_path: Optional[str]
    on_event: Optional[object]
    config: dict


# ── Nodes ─────────────────────────────────────────────────────────────────────

def think_node(state: AgentState) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    clean_messages = []
    for m in state["messages"]:
        if isinstance(m, dict):
            clean_messages.append({k: v for k, v in m.items() if k != "_response"})
        else:
            clean_messages.append(m)

    response = client.messages.create(
        model=state["model"],
        max_tokens=8192,
        system=state["system_prompt"],
        tools=TOOL_SCHEMAS,
        messages=clean_messages,
        temperature=0,
    )

    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    cost = token_cost(state["model"], tokens_in, tokens_out)

    on_event = state.get("on_event")
    if on_event:
        on_event("token_usage", {
            "iteration": state["iter_count"],
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost,
            "cumulative_cost_usd": state["cumulative_cost_usd"] + cost,
        })

    assistant_msg = {
        "role": "assistant",
        "content": response.content,
        "_response": response,
    }

    text = ""
    for block in response.content:
        if hasattr(block, "type") and block.type == "text":
            text += block.text

    final_report = state.get("final_report", "")
    if "## Executive Summary" in text and len(text) > 1500:
        final_report = text

    return {
        "messages": state["messages"] + [assistant_msg],
        "cumulative_tokens_in": state["cumulative_tokens_in"] + tokens_in,
        "cumulative_tokens_out": state["cumulative_tokens_out"] + tokens_out,
        "cumulative_cost_usd": state["cumulative_cost_usd"] + cost,
        "iter_count": state["iter_count"] + 1,
        "final_report": final_report,
    }


def tool_router(state: AgentState) -> str:
    if state["iter_count"] >= state["max_iter"]:
        return "end"

    last = state["messages"][-1]
    response = last.get("_response") if isinstance(last, dict) else None

    text = ""
    tool_calls = []
    if response:
        for block in response.content:
            if hasattr(block, "type") and block.type == "text":
                text += block.text
            elif hasattr(block, "type") and block.type == "tool_use":
                tool_calls.append(block)

    if "## Executive Summary" in text and len(text) > 1500:
        return "end"

    if tool_calls:
        return "tool_node"

    if is_v2_response(text):
        agent_out, _ = parse_agent_output(text)
        if agent_out and agent_out.next_action.decision in ("verdict", "abort"):
            return "end"

    if response and response.stop_reason == "end_turn" and not tool_calls:
        return "nudge"

    return "observe_node"


async def tool_node(state: AgentState) -> dict:
    last = state["messages"][-1]
    response = last.get("_response") if isinstance(last, dict) else None
    if not response:
        return {}

    tool_calls = [
        b for b in response.content
        if hasattr(b, "type") and b.type == "tool_use"
    ]
    if not tool_calls:
        return {}

    audit = AuditLog(state["audit_db"])
    on_event = state.get("on_event")
    tool_results = []

    for tool_call in tool_calls:
        if on_event:
            on_event("tool_call_start", {
                "tool": tool_call.name,
                "iteration": state["iter_count"],
                "args": tool_call.input,
            })

        result = await _dispatch_tool(tool_call.name, tool_call.input)

        audit.record(
            case_id=state["case_id"],
            tool_name=tool_call.name,
            tool_version="2.0.0",
            args=tool_call.input,
            outcome=result.outcome.value,
            output=result.model_dump_json(),
            duration_ms=result.duration_ms,
            agent_iteration=state["iter_count"],
            run_id=state["run_id"],
            tokens_in=state["cumulative_tokens_in"],
            tokens_out=state["cumulative_tokens_out"],
            cost_usd=0.0,
            correction_event=None,
        )

        if on_event:
            on_event("tool_call_end", {
                "tool": tool_call.name,
                "outcome": result.outcome.value,
                "summary": result.summary,
                "duration_ms": result.duration_ms,
                "iteration": state["iter_count"],
            })

        tool_results.append({
            "type": "tool_result",
            "tool_use_id": tool_call.id,
            "content": result.model_dump_json(indent=2)[:8000],
        })

    return {"messages": state["messages"] + [{"role": "user", "content": tool_results}]}


def nudge_node(state: AgentState) -> dict:
    return {
        "messages": state["messages"] + [{
            "role": "user",
            "content": (
                "Please compile your final incident report using the required headers, "
                "then append the JSON block with decision='verdict'."
            ),
        }]
    }


def observe_node(state: AgentState) -> dict:
    last_assistant = next(
        (m for m in reversed(state["messages"])
         if isinstance(m, dict) and m.get("role") == "assistant"),
        None,
    )
    if not last_assistant:
        return {}

    response = last_assistant.get("_response")
    text = ""
    final_report = state.get("final_report", "")

    if response:
        for block in response.content:
            if hasattr(block, "type") and block.type == "text":
                text += block.text
                if "## Executive Summary" in block.text:
                    final_report = block.text

    tool_calls = [
        b for b in (response.content if response else [])
        if hasattr(b, "type") and b.type == "tool_use"
    ]

    agent_out: Optional[AgentOutput] = None
    if not tool_calls and is_v2_response(text):
        agent_out, _ = parse_agent_output(text)
        if agent_out is None:
            agent_out = _synthesize_v1_fallback(text, state["iter_count"])
    elif tool_calls:
        agent_out = AgentOutput(
            iteration_summary=f"Tool calls: {[t.name for t in tool_calls]}",
            findings=[],
            hypotheses=[],
            next_action=NextAction(
                decision="continue", tool_to_call=None, rationale="tool turn"
            ),
            verdict=None,
        )
    else:
        agent_out = _synthesize_v1_fallback(text, state["iter_count"])

    new_findings = list(state["all_findings"])
    seen_keys = {(f["type"], f["value"].lower()) for f in new_findings}
    on_event = state.get("on_event")

    for f in (agent_out.findings if agent_out else []):
        key = (f.type, f.value.lower())
        if key not in seen_keys:
            new_findings.append(f.model_dump())
            seen_keys.add(key)
            if f.type in IOC_TYPES and on_event:
                on_event("ioc_detected", {
                    "type": f.type, "value": f.value,
                    "confidence": f.confidence,
                    "iteration": state["iter_count"],
                })

    hyp_dicts = [h.model_dump() for h in (agent_out.hypotheses if agent_out else [])]

    snap = SnapshotWriter(state["audit_db"])
    iocs = [f for f in new_findings if f.get("type") in IOC_TYPES]
    snap.write_iteration_snapshot(
        run_id=state["run_id"],
        case_id=state["case_id"],
        iteration=state["iter_count"],
        findings=new_findings,
        iocs=iocs,
        hypotheses=hyp_dicts,
        cumulative_tokens_in=state["cumulative_tokens_in"],
        cumulative_tokens_out=state["cumulative_tokens_out"],
        cumulative_cost_usd=state["cumulative_cost_usd"],
        wall_time_ms=0,
    )

    if on_event:
        on_event("iteration_complete", {
            "iteration": state["iter_count"],
            "findings_count": len(new_findings),
            "iocs_count": len(iocs),
            "cumulative_cost_usd": state["cumulative_cost_usd"],
        })

    return {
        "all_findings": new_findings,
        "all_hypotheses": hyp_dicts,
        "final_report": final_report,
    }


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("think_node", think_node)
    g.add_node("tool_node", tool_node)
    g.add_node("observe_node", observe_node)
    g.add_node("nudge_node", nudge_node)
    g.set_entry_point("think_node")
    g.add_conditional_edges("think_node", tool_router, {
        "tool_node": "tool_node",
        "observe_node": "observe_node",
        "nudge": "nudge_node",
        "end": END,
    })
    g.add_edge("tool_node", "observe_node")
    g.add_edge("observe_node", "think_node")
    g.add_edge("nudge_node", "think_node")
    return g.compile()


# ── Public entry point ────────────────────────────────────────────────────────

async def run_case_langgraph(
    case_id: str,
    evidence_files: dict[str, str],
    briefing: str,
    audit_db: str = "./audit/siftguard.db",
    training_mode: bool = False,
    model: str = DEFAULT_MODEL,
    config_override: Optional[dict] = None,
    ground_truth_path: Optional[str] = None,
    on_event: Optional[callable] = None,
) -> tuple[str, str]:
    run_id = str(uuid.uuid4())
    seed = (config_override or {}).get("seed", 0)
    max_iter = (config_override or {}).get("max_iterations", MAX_ITERATIONS)
    prompt_version = "v2_training" if training_mode else "v2"
    system_prompt = load_prompt(prompt_version)

    config = {
        "agent_id": "siftguard-langgraph",
        "model": model,
        "orchestrator": "langgraph",
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
        agent_id="siftguard-langgraph",
        config=config,
        ground_truth_path=ground_truth_path,
    )

    evidence_summary = "\n".join(f"- {k}: {v}" for k, v in evidence_files.items())
    initial_message = {
        "role": "user",
        "content": (
            f"## Case ID: {case_id}\n\n"
            f"## Briefing\n{briefing}\n\n"
            f"## Available Evidence\n{evidence_summary}\n\n"
            "Begin your investigation. Form an initial hypothesis. "
            "Remember to end every response with the required JSON block."
        ),
    }

    graph = build_graph()
    initial_state: AgentState = {
        "messages": [initial_message],
        "iter_count": 0,
        "max_iter": max_iter,
        "run_id": run_id,
        "case_id": case_id,
        "model": model,
        "system_prompt": system_prompt,
        "seed": seed,
        "all_findings": [],
        "all_hypotheses": [],
        "cumulative_tokens_in": 0,
        "cumulative_tokens_out": 0,
        "cumulative_cost_usd": 0.0,
        "final_report": "",
        "terminated_reason": "max_iterations",
        "audit_db": audit_db,
        "ground_truth_path": ground_truth_path,
        "on_event": on_event,
        "config": config,
    }

    if on_event:
        on_event("investigation_started", {
            "run_id": run_id, "case_id": case_id,
            "model": model, "orchestrator": "langgraph",
        })

    final_report = ""
    final_state: dict = initial_state
    terminated_reason = "error"
    try:
        final_state = await graph.ainvoke(initial_state)
        final_report = final_state.get("final_report") or (
            f"Investigation incomplete — max_iterations after "
            f"{final_state['iter_count']} iterations."
        )
        terminated_reason = "verdict_reached" if final_state.get("final_report") else "max_iterations"
    except Exception as e:
        logger.exception("LangGraph run failed: %s", e)
        final_report = f"Investigation aborted due to error: {e}"
        terminated_reason = "error"
        if on_event:
            on_event("error", {"message": str(e), "run_id": run_id})
    finally:
        try:
            snap.write_experiment_run_complete(
                run_id=run_id,
                completed_iterations=final_state.get("iter_count", 0) if isinstance(final_state, dict) else 0,
                terminated_reason=terminated_reason,
                total_tokens_in=final_state.get("cumulative_tokens_in", 0) if isinstance(final_state, dict) else 0,
                total_tokens_out=final_state.get("cumulative_tokens_out", 0) if isinstance(final_state, dict) else 0,
                total_cost_usd=final_state.get("cumulative_cost_usd", 0.0) if isinstance(final_state, dict) else 0.0,
            )
        except Exception as e:
            logger.warning("Failed to write experiment_run_complete: %s", e)

    return final_report, run_id