#!/usr/bin/env python3
"""T13 Phase 1: Inspect existing experiment runs for real-scorer readiness.
Checks each run's audit.db for tool_call rows + ioc_detected events.
Emits a coverage table — no API calls, no mutations.
"""
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

EXPERIMENTS_DIR = Path("experiments/runs")
AGENT_IDS = {
    "siftguard-v2": "Native",
    "siftguard-langgraph": "LangGraph",
    "siftguard-openai-fc": "OpenAI FC",
    "siftguard-gemini": "Gemini",
    "siftguard-claudecode": "Claude Code",
}


@dataclass
class RunCoverage:
    run_id: str
    agent_id: str
    agent_label: str
    audit_db_exists: bool
    tool_call_rows: int
    ioc_detected_rows: int
    verdict_reached: bool
    existing_f1: float | None
    scoreable: bool = field(init=False)

    def __post_init__(self):
        self.scoreable = (
            self.audit_db_exists
            and self.tool_call_rows > 0
            and self.ioc_detected_rows > 0
            and self.verdict_reached
        )


def get_existing_f1(run_dir: Path, agent_id: str) -> float | None:
    # Check experiments/analysis/<run_id>/data.json
    analysis_dirs = list(Path("experiments/analysis").glob("*/data.json"))
    for data_file in analysis_dirs:
        try:
            data = json.loads(data_file.read_text())
            panel7 = data.get("panel_7", {}).get("data", {})
            # Try both old key format and new agent_id format
            for key in [agent_id, agent_id.replace("siftguard-", "")]:
                if key in panel7:
                    return panel7[key].get("mean")
        except Exception:
            continue
    return None


def inspect_run(run_dir: Path) -> RunCoverage | None:
    meta_file = run_dir / "meta.json"
    if not meta_file.exists():
        return None

    try:
        meta = json.loads(meta_file.read_text())
    except Exception:
        return None

    agent_id = meta.get("agent_id", "unknown")
    agent_label = AGENT_IDS.get(agent_id, agent_id)
    run_id = run_dir.name

    audit_db = run_dir / "audit.db"
    if not audit_db.exists():
        return RunCoverage(
            run_id=run_id, agent_id=agent_id, agent_label=agent_label,
            audit_db_exists=False, tool_call_rows=0, ioc_detected_rows=0,
            verdict_reached=False, existing_f1=None,
        )

    try:
        con = sqlite3.connect(audit_db)
        cur = con.cursor()

        tool_calls = cur.execute(
            "SELECT COUNT(*) FROM agent_steps WHERE event_type='tool_call'"
        ).fetchone()[0]

        ioc_events = cur.execute(
            "SELECT COUNT(*) FROM agent_steps WHERE event_type='ioc_detected'"
        ).fetchone()[0]

        verdict = cur.execute(
            "SELECT COUNT(*) FROM experiment_runs WHERE terminated_reason='verdict_reached'"
        ).fetchone()[0]

        con.close()
    except Exception as e:
        print(f"  [warn] DB error in {run_dir}: {e}")
        return None

    existing_f1 = get_existing_f1(run_dir, agent_id)

    return RunCoverage(
        run_id=run_id, agent_id=agent_id, agent_label=agent_label,
        audit_db_exists=True, tool_call_rows=tool_calls,
        ioc_detected_rows=ioc_events, verdict_reached=bool(verdict),
        existing_f1=existing_f1,
    )


def main():
    if not EXPERIMENTS_DIR.exists():
        print(f"[error] {EXPERIMENTS_DIR} does not exist. Run from repo root.")
        return

    runs = sorted(EXPERIMENTS_DIR.iterdir())
    if not runs:
        print("[error] No runs found in experiments/runs/")
        return

    coverages: list[RunCoverage] = []
    for run_dir in runs:
        if not run_dir.is_dir():
            continue
        cov = inspect_run(run_dir)
        if cov:
            coverages.append(cov)

    # Print table
    header = f"{'Agent':<16} {'Run ID':<36} {'DB':>3} {'tool_calls':>10} {'ioc_events':>10} {'verdict':>8} {'existing_F1':>11} {'scoreable':>9}"
    print("\n" + "=" * len(header))
    print("T13 Phase 1 — Experiment Coverage Report")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    needs_rerun: list[RunCoverage] = []
    scoreable_count = 0

    for cov in coverages:
        f1_str = f"{cov.existing_f1:.3f}" if cov.existing_f1 is not None else "none"
        score_str = "YES" if cov.scoreable else "NO"
        print(
            f"{cov.agent_label:<16} {cov.run_id:<36} "
            f"{'Y' if cov.audit_db_exists else 'N':>3} "
            f"{cov.tool_call_rows:>10} {cov.ioc_detected_rows:>10} "
            f"{'Y' if cov.verdict_reached else 'N':>8} "
            f"{f1_str:>11} {score_str:>9}"
        )
        if not cov.scoreable:
            needs_rerun.append(cov)
        else:
            scoreable_count += 1

    print("=" * len(header))
    print(f"\nSummary: {scoreable_count}/{len(coverages)} runs scoreable without API calls")

    if needs_rerun:
        print("\nRuns requiring re-run (estimate cost before triggering):")
        cost_map = {
            "siftguard-v2": 0.05,
            "siftguard-langgraph": 0.10,
            "siftguard-openai-fc": 0.25,
            "siftguard-gemini": 0.05,
            "siftguard-claudecode": 0.65,
        }
        total_estimated = 0.0
        for r in needs_rerun:
            cost = cost_map.get(r.agent_id, 0.20)
            total_estimated += cost
            print(f"  - {r.agent_label:<16} (agent_id={r.agent_id}) ~${cost:.2f}")
        print(f"\n  Total estimated re-run cost: ~${total_estimated:.2f}")
        print("  >>> Confirm spend before triggering any re-runs <<<")
    else:
        print("\nAll runs scoreable — Phase 2 (re-runs) can be skipped entirely.")


if __name__ == "__main__":
    main()
