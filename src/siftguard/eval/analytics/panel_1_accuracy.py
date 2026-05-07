"""Panel 1 — Accuracy curve over iterations.

Claim: SIFTGuard accuracy improves with iteration count and plateaus.
Self-correction is responsible for the improvement.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.axes

from siftguard.eval.analytics.style import apply_style, add_claim, placeholder, BLUE, GRAY, LGRAY
from siftguard.eval.analytics.load_traces import (
    load_iteration_snapshots, get_db_path, load_experiment_runs_from_db
)
from siftguard.eval.analytics.scorer_framework import score_findings, ScoreResult
from siftguard.eval.trace import Finding, FindingType

CLAIM = "Accuracy improves monotonically with iteration count and plateaus — self-correction drives improvement."
GT_DIR = Path(__file__).resolve().parents[4] / "tests" / "benchmark" / "ground_truth"


def _findings_from_snapshot(snap: dict) -> list[Finding]:
    findings = []
    seen: set[tuple] = set()
    raw_list = json.loads(snap.get("findings_json") or "[]")
    for raw in raw_list:
        try:
            ftype = FindingType(raw.get("type", "other"))
        except ValueError:
            ftype = FindingType.OTHER
        value = str(raw.get("value", ""))
        key = (ftype.value, value.lower())
        if key in seen:
            continue
        seen.add(key)
        excerpt = str(raw.get("evidence_excerpt", value))[:200]
        if len(excerpt) < 10:
            excerpt = (excerpt + " " * 10)[:10]
        findings.append(Finding(
            id=raw.get("id", f"{ftype.value}-{value}"),
            type=ftype,
            value=value,
            confidence=raw.get("confidence"),
            supporting_audit_entry_ids=[],
            evidence_excerpt=excerpt,
            mitre_technique=raw.get("mitre_technique"),
            first_seen_iteration=raw.get("first_seen_iteration", 0),
        ))
    return findings


def render(ax: matplotlib.axes.Axes, case_id: str = "TEST-001") -> dict:
    apply_style()
    db_path = get_db_path(case_id)
    gt_path = GT_DIR / f"{case_id}.json"

    if not db_path.exists() or not gt_path.exists():
        placeholder(ax, "Panel 1 — Accuracy over Iterations",
                    f"DB not found: {db_path}")
        return {"status": "placeholder"}

    runs = load_experiment_runs_from_db(db_path)
    if not runs:
        placeholder(ax, "Panel 1 — Accuracy over Iterations",
                    "No experiment runs found in DB.")
        return {"status": "placeholder"}

    plotted = 0
    data_out = {}

    for run in runs:
        run_id = run["run_id"]
        config = json.loads(run.get("config_json") or "{}")
        label = config.get("notes", run_id[:8])
        if not label or label == run_id[:8]:
            label = f"{config.get('agent_id','?')} {config.get('prompt_version','')}"

        snapshots = load_iteration_snapshots(db_path, run_id)
        if not snapshots:
            continue

        iterations = []
        f1_scores  = []
        for snap in snapshots:
            findings = _findings_from_snapshot(snap)
            score = score_findings(findings, gt_path)
            iterations.append(snap["iteration"])
            f1_scores.append(score.f1)

        if not iterations:
            continue

        ax.plot(iterations, f1_scores, marker="o", label=label)
        data_out[run_id] = {"iterations": iterations, "f1": f1_scores}
        plotted += 1

    if plotted == 0:
        placeholder(ax, "Panel 1 — Accuracy over Iterations",
                    "No iteration snapshots found. Re-run experiments with v2 loop.")
        return {"status": "placeholder"}

    ax.set_title("Panel 1 — Accuracy over Iterations", fontweight="bold")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("IOC F1 Score")
    ax.set_ylim(0, 1.05)
    ax.legend(loc="lower right", fontsize=7)
    add_claim(ax, CLAIM)
    return {"status": "ok", "data": data_out}