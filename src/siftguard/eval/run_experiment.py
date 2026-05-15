"""Thin experiment runner — dispatches to per-orchestrator adapters.

Usage:
    python3 -m siftguard.eval.run_experiment --orchestrator siftguard-langgraph --case TEST-002
"""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]


async def run(orchestrator: str, case_id: str) -> None:
    from siftguard.cases.loader import get_case, evidence_paths

    manifest = get_case(case_id)
    ev_paths = evidence_paths(manifest)
    evidence = {k: str(v) for k, v in ev_paths.items()}
    briefing = manifest.briefing
    audit_db = str(REPO_ROOT / "audit" / f"{case_id}.db")

    log.info("orchestrator=%s case=%s", orchestrator, case_id)
    log.info("evidence=%s", evidence)

    def on_event(event_type: str, data: dict) -> None:
        log.info("[event] %s %s", event_type, list(data.keys()))

    if orchestrator == "siftguard-langgraph":
        from siftguard.orchestrators.langgraph_adapter import run_case_langgraph
        result = await run_case_langgraph(
            case_id=case_id, evidence_files=evidence,
            briefing=briefing, audit_db=audit_db, on_event=on_event,
        )
    elif orchestrator == "siftguard-openai-fc":
        from siftguard.orchestrators.openai_fc_adapter import run_case_openai_fc
        result = await run_case_openai_fc(
            case_id=case_id, evidence_files=evidence,
            briefing=briefing, audit_db=audit_db, on_event=on_event,
        )
    elif orchestrator == "siftguard-gemini":
        from siftguard.orchestrators.gemini_adapter import run_case_gemini
        result = await run_case_gemini(
            case_id=case_id, evidence_files=evidence,
            briefing=briefing, audit_db=audit_db, on_event=on_event,
        )
    elif orchestrator == "siftguard-claudecode":
        from siftguard.eval.orchestrators.claude_code_adapter import ClaudeCodeAdapter
        adapter = ClaudeCodeAdapter()
        result = await asyncio.get_running_loop().run_in_executor(
            None, lambda: adapter.run(case_id, briefing)
        )
    elif orchestrator == "siftguard-v2":
        from siftguard.agent.loop import run_case
        result = await run_case(
            case_id=case_id, evidence_files=evidence,
            briefing=briefing, audit_db=audit_db, on_event=on_event,
        )
    else:
        log.error("Unknown orchestrator: %s", orchestrator)
        sys.exit(1)

    out_dir = REPO_ROOT / "experiments" / "results" / f"{orchestrator.replace('siftguard-', 'baseline_')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / case_id / f"result_{ts}.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    payload = result if isinstance(result, dict) else (result.report if hasattr(result, "report") else {"raw": str(result)})
    out_file.write_text(json.dumps(payload, indent=2, default=str))
    log.info("result written to %s", out_file)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orchestrator", required=True)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.orchestrator, args.case))


if __name__ == "__main__":
    main()