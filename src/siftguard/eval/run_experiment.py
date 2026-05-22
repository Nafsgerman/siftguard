"""SIFTGuard unified experiment runner.

CLI:
    python -m siftguard.eval.run_experiment --agent <id> --case <CASE_ID> [--gt-version 1.1.0]

Aliases for --agent: native | langgraph | openai-fc | gemini | claudecode
(canonical: siftguard-v2, siftguard-langgraph, siftguard-openai-fc,
            siftguard-gemini, siftguard-claudecode)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_experiment")

REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_DIR = REPO_ROOT / "audit"
RESULTS_DIR = REPO_ROOT / "experiments" / "results"

AGENT_ALIASES: dict[str, str] = {
    "native": "siftguard-v2",
    "v2": "siftguard-v2",
    "siftguard-v2": "siftguard-v2",
    "langgraph": "siftguard-langgraph",
    "siftguard-langgraph": "siftguard-langgraph",
    "openai-fc": "siftguard-openai-fc",
    "openai_fc": "siftguard-openai-fc",
    "openai": "siftguard-openai-fc",
    "siftguard-openai-fc": "siftguard-openai-fc",
    "gemini": "siftguard-gemini",
    "siftguard-gemini": "siftguard-gemini",
    "claudecode": "siftguard-claudecode",
    "claude-code": "siftguard-claudecode",
    "siftguard-claudecode": "siftguard-claudecode",
}


def normalize_agent_id(raw: str) -> str:
    key = raw.strip().lower()
    if key not in AGENT_ALIASES:
        raise SystemExit(f"Unknown agent '{raw}'. Valid: {sorted(set(AGENT_ALIASES.keys()))}")
    return AGENT_ALIASES[key]


def _audit_db_for(case_id: str) -> str:
    return str(AUDIT_DIR / f"{case_id.replace('TEST-', 'CASE-')}.db")


async def _dispatch(
    agent_id: str,
    case_id: str,
    evidence: dict[str, str],
    briefing: str,
    audit_db: str,
    manifest: Any = None,
    self_correction: bool = True,
) -> tuple[Any, Optional[str]]:
    from siftguard.agent.system_prompt_gate import build_system_prompt_prefix
    from siftguard.cases.tool_injection import build_tools_preamble, manifest_from_case_loader
    from siftguard.eval.scorer import get_last_run_id

    preamble = build_tools_preamble(manifest_from_case_loader(manifest)) if manifest else ""
    system_prefix = build_system_prompt_prefix(self_correction, preamble)

    result = None
    if agent_id == "siftguard-langgraph":
        from siftguard.orchestrators.langgraph_adapter import run_case_langgraph

        result = await run_case_langgraph(
            case_id=case_id,
            evidence_files=evidence,
            briefing=briefing,
            audit_db=audit_db,
            on_event=None,
            system_prompt_prefix=system_prefix,
        )
    elif agent_id == "siftguard-openai-fc":
        from siftguard.orchestrators.openai_fc_adapter import run_case_openai_fc

        result = await run_case_openai_fc(
            case_id=case_id,
            evidence_files=evidence,
            briefing=briefing,
            audit_db=audit_db,
            on_event=None,
            system_prompt_prefix=system_prefix,
        )
    elif agent_id == "siftguard-gemini":
        from siftguard.orchestrators.gemini_adapter import run_case_gemini

        result = await run_case_gemini(
            case_id=case_id,
            evidence_files=evidence,
            briefing=briefing,
            audit_db=audit_db,
            on_event=None,
            system_prompt_prefix=system_prefix,
        )
    elif agent_id == "siftguard-claudecode":
        from siftguard.eval.orchestrators.claude_code_adapter import ClaudeCodeAdapter

        adapter = ClaudeCodeAdapter()
        result = await asyncio.get_running_loop().run_in_executor(
            None, lambda: adapter.run(case_id, system_prefix + briefing)
        )
    elif agent_id == "siftguard-v2":
        from siftguard.agent.loop import run_case

        result = await run_case(
            case_id=case_id,
            evidence_files=evidence,
            briefing=briefing,
            audit_db=audit_db,
            on_event=None,
            system_prompt_prefix=system_prefix,
        )
    else:
        raise SystemExit(f"Unhandled agent_id: {agent_id}")

    run_id = get_last_run_id(audit_db, agent_id, case_id)
    return result, run_id


def _write_raw_result(agent_id: str, case_id: str, payload: Any, ts: str) -> Path:
    from siftguard.agent.output_validator import parse_agent_output

    out_dir = RESULTS_DIR / agent_id.replace("siftguard-", "baseline_") / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"result_{ts}.json"

    raw_text = (
        payload
        if isinstance(payload, str)
        else (payload.report if hasattr(payload, "report") else None)
    )

    if isinstance(raw_text, str):
        parsed, _err = parse_agent_output(raw_text)
        if parsed is not None:
            body: Any = {
                "report_text": raw_text,
                "parsed": parsed.model_dump(mode="json"),
            }
        else:
            body = raw_text
    else:
        body = payload if isinstance(payload, dict | list | int | float) else {"raw": str(payload)}

    out_file.write_text(json.dumps(body, indent=2, default=str))
    return out_file


async def _run(agent_id: str, case_id: str, gt_version: str) -> int:
    from siftguard.cases.loader import get_case as load_manifest
    from siftguard.eval.panel_7_writer import update_panel_7
    from siftguard.eval.scorer import score_run

    manifest = load_manifest(case_id)
    evidence = {ef["type"]: ef["path"] for ef in manifest.evidence_files}
    briefing = (
        manifest.briefing
        if hasattr(manifest, "briefing") and manifest.briefing
        else f"Investigate evidence for case {case_id}. Report all IOCs."
    )
    audit_db = _audit_db_for(case_id)

    log.info("agent=%s case=%s gt=v%s audit_db=%s", agent_id, case_id, gt_version, audit_db)
    log.info("evidence=%s", evidence)

    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    result, run_id = await _dispatch(agent_id, case_id, evidence, briefing, audit_db, manifest)
    out_file = _write_raw_result(agent_id, case_id, result, ts)
    log.info("raw result -> %s", out_file)
    log.info("run_id=%s", run_id)

    score = None
    if run_id:
        try:
            score = score_run(
                case_id=case_id,
                agent_id=agent_id,
                gt_version=gt_version,
                audit_db_path=audit_db,
                run_id=run_id,
            )
        except FileNotFoundError as exc:
            log.warning("GT file not found (%s) -- skipping score", exc)
    if score:
        log.info(
            "f1_applicable=%s tp=%d fp=%d fn=%d applicable=%d total=%d",
            f"{score.f1_applicable:.3f}" if score.f1_applicable is not None else "None",
            score.tp,
            score.fp,
            score.fn_applicable,
            score.applicable_count,
            score.total_count,
        )
        data_path = update_panel_7(
            case_id=case_id,
            agent_id=agent_id,
            f1=score.f1_applicable,
            gt_version=gt_version,
            applicable_count=score.applicable_count,
            not_applicable_count=score.total_count - score.applicable_count,
            run_timestamp=ts,
        )
        log.info("panel_7 updated -> %s", data_path)
        (out_file.with_suffix(".score.json")).write_text(json.dumps(score.to_dict(), indent=2))
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="run_experiment")
    p.add_argument("--agent", help="Agent ID or alias (e.g. langgraph, openai-fc, native)")
    p.add_argument("--orchestrator", help="DEPRECATED: use --agent")
    p.add_argument("--case", required=True, help="Case ID, e.g. TEST-001")
    p.add_argument(
        "--gt-version", default="1.1.0", help="Ground truth schema version (default 1.1.0)"
    )
    args = p.parse_args(argv)

    raw = args.agent or args.orchestrator
    if not raw:
        p.error("one of --agent / --orchestrator is required")
    if args.orchestrator and not args.agent:
        log.warning("--orchestrator is deprecated; use --agent")
    args.agent_canonical = normalize_agent_id(raw)
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return asyncio.run(_run(args.agent_canonical, args.case, args.gt_version))


if __name__ == "__main__":
    sys.exit(main())
