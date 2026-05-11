"""Gemini orchestrator adapter for SIFTGuard.

Single-variable claim: orchestration changes, model/tools/scorer unchanged.
Uses Google Gemini API with function calling via google-genai SDK.
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
    from google import genai
    from google.genai import types as gtypes
except ImportError:
    raise ImportError("pip install google-genai")

from siftguard.agent.instrumentation import SnapshotWriter, token_cost
from siftguard.agent.loop_v2 import (
    MAX_ITERATIONS,
    TOOL_SCHEMAS,
    _dispatch_tool,
)
from siftguard.agent.output_schema import NextAction
from siftguard.agent.output_validator import is_v2_response, parse_agent_output
from siftguard.agent.prompts import load_prompt
from siftguard.audit.log import AuditLog

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")


def _to_gemini_tools() -> list:
    tools = []
    for t in TOOL_SCHEMAS:
        schema = t.get("input_schema", {})
        props = {}
        for k, v in schema.get("properties", {}).items():
            props[k] = gtypes.Schema(
                type=gtypes.Type.STRING,
                description=v.get("description", ""),
            )
        tools.append(gtypes.Tool(
            function_declarations=[gtypes.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=gtypes.Schema(
                    type=gtypes.Type.OBJECT,
                    properties=props,
                    required=schema.get("required", []),
                ),
            )]
        ))
    return tools


GEMINI_TOOLS = _to_gemini_tools()


async def run_case_gemini(
    case_id: str,
    evidence_files: dict[str, str],
    briefing: str,
    audit_db: str = "./audit/siftguard.db",
    training_mode: bool = False,
    model: str = GEMINI_MODEL,
    config_override: Optional[dict] = None,
    ground_truth_path: Optional[str] = None,
    on_event: Optional[callable] = None,
) -> tuple[str, str]:
    run_id = str(uuid.uuid4())
    max_iter = (config_override or {}).get("max_iterations", MAX_ITERATIONS)
    prompt_version = "v2_training" if training_mode else "v2"
    system_prompt = load_prompt(prompt_version)

    config = {
        "agent_id": "siftguard-gemini",
        "model": model,
        "orchestrator": "gemini",
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
        agent_id="siftguard-gemini",
        config=config,
        ground_truth_path=ground_truth_path,
    )

    audit = AuditLog(db_path=audit_db)
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    evidence_summary = "\n".join(f"- {k}: {v}" for k, v in evidence_files.items())
    initial_text = (
        f"## Case ID: {case_id}\n\n"
        f"## Briefing\n{briefing}\n\n"
        f"## Available Evidence\n{evidence_summary}\n\n"
        "Begin your investigation. Form an initial hypothesis. "
        "Remember to end every response with the required JSON block."
    )

    if on_event:
        on_event("investigation_started", {"case_id": case_id, "briefing": briefing})

    history = [{"role": "user", "parts": [{"text": initial_text}]}]

    all_findings: list[dict] = []
    all_hypotheses: list[dict] = []
    cumulative_tokens_in = 0
    cumulative_tokens_out = 0
    cumulative_cost = 0.0
    final_report = ""
    terminated_reason = "max_iterations"
    iter_count = 0

    for iteration in range(max_iter):
        iter_count = iteration

        if on_event:
            on_event("iteration_complete", {
                "iteration": iteration,
                "max": max_iter,
                "findings": all_findings,
                "hypotheses": all_hypotheses,
            })

        try:
            response = client.models.generate_content(
                model=model,
                contents=history,
                config=gtypes.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=GEMINI_TOOLS,
                ),
            )
        except Exception as e:
            logger.error("Gemini API error at iteration %d: %s", iteration, e)
            terminated_reason = "error"
            break

        tokens_in = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        tokens_out = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
        cost = token_cost("gemini-2.5-pro", tokens_in, tokens_out)
        cumulative_tokens_in += tokens_in
        cumulative_tokens_out += tokens_out
        cumulative_cost += cost

        if not response.candidates:
            logger.warning("Gemini returned no candidates at iteration %d", iteration)
            break

        candidate = response.candidates[0]
        text_parts = []
        tool_calls = []

        for part in candidate.content.parts:
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)
            if hasattr(part, "function_call") and part.function_call and part.function_call.name:
                tool_calls.append(part.function_call)

        agent_text = "\n".join(text_parts).strip()

        if agent_text and on_event:
            on_event("agent_text", {"text": agent_text, "iteration": iteration})

        history.append({"role": "model", "parts": candidate.content.parts})

        if tool_calls:
            tool_result_parts = []
            for fc in tool_calls:
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}

                if on_event:
                    on_event("tool_call_start", {"tool": tool_name, "args": tool_args})

                result = await _dispatch_tool(tool_name, tool_args)
                outcome = "ok" if result.outcome == "ok" else "fail"
                summary = result.summary or ""
                duration_ms = result.duration_ms or 0

                audit.record(
                    case_id=case_id,
                    tool_name=tool_name,
                    tool_version="1.0",
                    args=tool_args,
                    outcome=outcome,
                    output=summary,
                    duration_ms=duration_ms,
                    agent_iteration=iteration,
                    hypothesis_id=run_id,
                )

                if on_event:
                    on_event("tool_call_end", {
                        "tool": tool_name,
                        "outcome": outcome,
                        "summary": summary,
                        "findings_count": len(result.findings or []),
                        "duration_ms": duration_ms,
                    })

                tool_result_parts.append(gtypes.Part(
                    function_response=gtypes.FunctionResponse(
                        name=tool_name,
                        response={"result": json.dumps(result.model_dump(), default=str)},
                    )
                ))

            history.append({"role": "user", "parts": tool_result_parts})
            continue

        if not agent_text:
            history.append({"role": "user", "parts": [{"text": "Continue your investigation."}]})
            continue

        parsed = parse_agent_output(agent_text) if is_v2_response(agent_text) else None

        if parsed:
            if parsed.findings:
                all_findings.extend([f.model_dump() for f in parsed.findings])
            if parsed.hypotheses:
                all_hypotheses.extend([h.model_dump() for h in parsed.hypotheses])
                if on_event:
                    for h in parsed.hypotheses:
                        on_event("hypothesis_update", {"hypothesis": h.model_dump()})

            if parsed.verdict and parsed.next_action.decision == NextAction.VERDICT:
                final_report = agent_text
                terminated_reason = "verdict_reached"
                if on_event:
                    on_event("verdict_reached", {
                        "verdict": parsed.verdict.model_dump(),
                        "findings": all_findings,
                    })
                break

        history.append({"role": "user", "parts": [{"text": "Continue your investigation."}]})

    snap.write_experiment_run_complete(
        run_id=run_id,
        completed_iterations=iter_count,
        terminated_reason=terminated_reason,
        total_tokens_in=cumulative_tokens_in,
        total_tokens_out=cumulative_tokens_out,
        total_cost_usd=cumulative_cost,
    )

    return final_report or "Investigation incomplete.", run_id