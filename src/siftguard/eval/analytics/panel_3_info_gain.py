"""Panel 3 — Information gain per tool call.

Claim: Marginal information from each tool call diminishes after call N.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.axes

from siftguard.eval.analytics.style import (
    apply_style, add_claim, placeholder, BLUE, GREEN, GRAY
)
from siftguard.eval.analytics.load_traces import (
    load_iteration_snapshots, load_audit_entries,
    get_db_path, load_experiment_runs_from_db
)
from siftguard.eval.analytics.scorer_framework import score_findings
from siftguard.eval.trace import Finding, FindingType

CLAIM = "Marginal information gain diminishes after tool call N — justifying the max-iterations cap."
GT_DIR = Path(__file__).resolve().parents[4] / "tests" / "benchmark" / "ground_truth"


def _findings_from_json(raw_list: list) -> list[Finding]:
    findings = []
    seen: set[tuple] = set()
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
            first_seen_iteration=raw.get("first_seen_iteration", 0),
        ))
    return findings


def render(ax: matplotlib.axes.Axes, case_id: str = "TEST-001") -> dict:
    apply_style()
    db_path = get_db_path(case_id)
    gt_path = GT_DIR / f"{case_id}.json"

    if not db_path.exists():
        placeholder(ax, "Panel 3 — Info Gain per Tool Call",
                    f"DB not found: {db_path}")
        return {"status": "placeholder"}

    runs = load_experiment_runs_from_db(db_path)
    baseline_run = next(
        (r for r in runs
         if json.loads(r.get("config_json") or "{}").get("notes", "")
         .startswith("Primary baseline")),
        runs[0] if runs else None,
    )

    if not baseline_run:
        placeholder(ax, "Panel 3 — Info Gain per Tool Call",
                    "No runs found.")
        return {"status": "placeholder"}

    run_id   = baseline_run["run_id"]
    snapshots = load_iteration_snapshots(db_path, run_id)

    if len(snapshots) < 2:
        placeholder(ax, "Panel 3 — Info Gain per Tool Call",
                    f"Need >= 2 iteration snapshots (found {len(snapshots)}).")
        return {"status": "placeholder"}

    f1_series = []
    for snap in snapshots:
        findings = _findings_from_json(
            json.loads(snap.get("findings_json") or "[]")
        )
        score = score_findings(findings, gt_path)
        f1_series.append(score.f1)

    deltas = [0.0] + [
        max(0.0, f1_series[i] - f1_series[i - 1])
        for i in range(1, len(f1_series))
    ]
    iterations = list(range(len(deltas)))

    ax.bar(iterations, deltas, color=BLUE, alpha=0.8, width=0.6)
    ax.axhline(0.02, color=GREEN, linestyle="--", linewidth=1.5,
               label="ε = 0.02 threshold")

    ax.set_title("Panel 3 — Info Gain per Tool Call", fontweight="bold")
    ax.set_xlabel("Iteration Index")
    ax.set_ylabel("Marginal F1 Gain (ΔF1)")
    ax.legend(fontsize=8)
    add_claim(ax, CLAIM)

    return {
        "status": "ok",
        "run_id": run_id,
        "f1_series": f1_series,
        "deltas": deltas,
    }