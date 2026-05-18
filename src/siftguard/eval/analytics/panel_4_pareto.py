"""Panel 4 — Cost-accuracy Pareto frontier.

Claim: Optimal operating point is N iterations at $X cost.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.axes

from siftguard.eval.analytics.load_traces import (
    get_db_path,
    load_experiment_runs_from_db,
    load_iteration_snapshots,
)
from siftguard.eval.analytics.scorer_framework import score_findings
from siftguard.eval.analytics.style import (
    BLUE,
    GRAY,
    add_claim,
    apply_style,
    placeholder,
)
from siftguard.eval.trace import Finding, FindingType

CLAIM = (
    "The Pareto frontier identifies the optimal accuracy-per-dollar operating point for deployment."
)
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
        findings.append(
            Finding(
                id=raw.get("id", f"{ftype.value}-{value}"),
                type=ftype,
                value=value,
                confidence=raw.get("confidence"),
                supporting_audit_entry_ids=[],
                evidence_excerpt=excerpt,
                first_seen_iteration=raw.get("first_seen_iteration", 0),
            )
        )
    return findings


def _is_pareto(costs: list, f1s: list) -> list[bool]:
    n = len(costs)
    on_frontier = [True] * n
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if (
                costs[j] <= costs[i]
                and f1s[j] >= f1s[i]
                and (costs[j] < costs[i] or f1s[j] > f1s[i])
            ):
                on_frontier[i] = False
                break
    return on_frontier


def render(ax: matplotlib.axes.Axes, case_id: str = "TEST-001") -> dict:
    apply_style()
    db_path = get_db_path(case_id)
    gt_path = GT_DIR / f"{case_id}.json"

    if not db_path.exists():
        placeholder(ax, "Panel 4 — Cost-Accuracy Pareto", f"DB not found: {db_path}")
        return {"status": "placeholder"}

    runs = load_experiment_runs_from_db(db_path)
    if not runs:
        placeholder(ax, "Panel 4 — Cost-Accuracy Pareto", "No experiment runs found.")
        return {"status": "placeholder"}

    points = []
    for run in runs:
        run_id = run["run_id"]
        config = json.loads(run.get("config_json") or "{}")
        cost = run.get("total_cost_usd") or 0.0
        snapshots = load_iteration_snapshots(db_path, run_id)
        if not snapshots:
            continue
        last = snapshots[-1]
        findings = _findings_from_json(json.loads(last.get("findings_json") or "[]"))
        score = score_findings(findings, gt_path)
        label = config.get("notes", run_id[:8])
        if not label or len(label) > 30:
            label = f"{config.get('prompt_version', '?')} iter={config.get('max_iterations', '?')}"
        points.append(
            {
                "cost": cost,
                "f1": score.f1,
                "label": label,
                "is_v1": config.get("prompt_version", "v2") == "v1",
            }
        )

    if not points:
        placeholder(ax, "Panel 4 — Cost-Accuracy Pareto", "No scored runs found.")
        return {"status": "placeholder"}

    costs = [p["cost"] for p in points]
    f1s = [p["f1"] for p in points]
    on_f = _is_pareto(costs, f1s)

    for _i, (p, frontier) in enumerate(zip(points, on_f, strict=False)):
        color = BLUE if frontier else GRAY
        marker = "*" if frontier else "o"
        size = 120 if frontier else 60
        ax.scatter(p["cost"], p["f1"], c=color, marker=marker, s=size, zorder=3, alpha=0.85)
        ax.annotate(
            p["label"][:20],
            (p["cost"], p["f1"]),
            textcoords="offset points",
            xytext=(5, 4),
            fontsize=6,
            color=GRAY,
        )

    frontier_pts = sorted(
        [(c, f) for c, f, on in zip(costs, f1s, on_f, strict=False) if on],
        key=lambda x: x[0],
    )
    if len(frontier_pts) > 1:
        fx, fy = zip(*frontier_pts, strict=False)
        ax.step(
            fx,
            fy,
            where="post",
            color=BLUE,
            linewidth=1.5,
            linestyle="--",
            alpha=0.5,
            label="Pareto frontier",
        )

    ax.set_title("Panel 4 — Cost-Accuracy Pareto Frontier", fontweight="bold")
    ax.set_xlabel("Total Cost (USD)")
    ax.set_ylabel("IOC F1 Score")
    ax.legend(fontsize=8)
    add_claim(ax, CLAIM)

    return {
        "status": "ok",
        "points": points,
        "frontier": frontier_pts,
    }
