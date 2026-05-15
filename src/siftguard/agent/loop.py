"""SIFTGuard agent loop — public dispatch entry point.

Routes to v1 (baseline, frozen) or v2 (instrumented, structured-confidence)
based on the prompt_version config value.

ADR: docs/adr/ADR-004-loop-instrumentation.md
"""
from __future__ import annotations

import os
from typing import Optional

from siftguard.agent.loop_v1 import run_case_v1
from siftguard.agent.loop_v2 import run_case_v2


async def run_case(
    case_id: str,
    evidence_files: dict[str, str],
    briefing: str,
    audit_db: str = "./audit/siftguard.db",
    training_mode: bool = False,
    model: Optional[str] = None,
    prompt_version: Optional[str] = None,
    config_override: Optional[dict] = None,
    ground_truth_path: Optional[str] = None,
    on_event: Optional[callable] = None,
) -> str:
    """
    Public entry point. Returns final incident report string.

    prompt_version="v1" or "v1_training" → v1 loop (frozen baseline)
    prompt_version="v2" or "v2_training" → v2 loop (instrumented)
    Default: v2
    """
    _version = prompt_version or os.environ.get("SIFTGUARD_PROMPT_VERSION", "v2")
    _model   = model or os.environ.get("SIFTGUARD_MODEL", "claude-sonnet-4-6")

    _orchestrator = (config_override or {}).get("orchestrator", "siftguard-native")
    if _orchestrator == "langgraph":
        from siftguard.orchestrators.langgraph_adapter import run_case_langgraph
        report, _run_id = await run_case_langgraph(
            case_id=case_id,
            evidence_files=evidence_files,
            briefing=briefing,
            audit_db=audit_db,
            training_mode=training_mode,
            model=_model,
            config_override=config_override,
            ground_truth_path=ground_truth_path,
            on_event=on_event,
        )
        return report

    if _version.startswith("v1"):
        return await run_case_v1(
            case_id=case_id,
            evidence_files=evidence_files,
            briefing=briefing,
            audit_db=audit_db,
            training_mode=training_mode,
        )

    report, _run_id = await run_case_v2(
        case_id=case_id,
        evidence_files=evidence_files,
        briefing=briefing,
        audit_db=audit_db,
        training_mode=training_mode,
        model=_model,
        config_override=config_override,
        ground_truth_path=ground_truth_path,
        on_event=on_event,
    )
    return report
