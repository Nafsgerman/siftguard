"""Panel 6 — Ablation grid.

Claim: Self-correction adds X F1 points. v2 prompt adds Y. Correlation adds Z.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.axes
import numpy as np

from siftguard.eval.analytics.style import (
    apply_style, add_claim, placeholder, BLUE, GREEN, YELLOW, RED, GRAY
)
from siftguard.eval.analytics.load_traces import (
    load_iteration_snapshots, get_db_path, load_experiment_runs_from_db
)
from siftguard.eval.analytics.scorer_framework import score_findings
from siftguard.eval.trace import Finding, FindingType

CLAIM = "Each feature's contribution is measured independently. Ablation reveals what actually matters."
GT_DIR = Path(__file__).resolve().parents[4] / "tests" / "benchmark" / "ground_truth"

# Match by notes prefix — unique per config, set in experiments/configs/*.json
CONFIG_DISPLAY = [
    ("Primary baseline",          "Baseline\n(all on)",         BLUE),
    ("Ablation: self_correction", "No self-\ncorrection",       YELLOW),
    ("Ablation: correlation",     "No\ncorrelation",            GREEN),
    ("v1 baseline",               "v1 prompt\n(no confidence)", RED),
]


def _find_run_by_notes(runs: list[dict], notes_prefix: str) -> dict | None:
    """Find the most recent run whose notes start with the given prefix."""
    candidates = []
    for run in runs:
        cfg = json.loads(run.get("config_json") or "{}")
        notes = cfg.get("notes", "")
        if notes.startswith(notes_prefix):
            candidates.append(run)
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.get("started_at", ""))


def _score_run(run: dict, db_path: Path, gt_path: Path) -> float:
    run_id = run["run_id"]
    snapshots = load_iteration_snapshots(db_path, run_id)
    if not snapshots:
        return 0.0
    last = snapshots[-1]
    raw_list = json.loads(last.get("findings_json") or "[]")
    findings = []
    seen: set[tuple] = set()
    valid_types = {t.value for t in FindingType}
    for raw in raw_list:
        ftype_str = raw.get("type", "other")
        if ftype_str not in valid_types:
            ftype_str = "other"
        value = str(raw.get("value", ""))
        key = (ftype_str, value.lower())
        if key in seen:
            continue
        seen.add(key)
        excerpt = str(raw.get("evidence_excerpt", value))[:200]
        if len(excerpt) < 10:
            excerpt = (excerpt + " " * 10)[:10]
        findings.append(Finding(
            id=raw.get("id", f"{ftype_str}-{value}"),
            type=FindingType(ftype_str),
            value=value,
            confidence=raw.get("confidence"),
            supporting_audit_entry_ids=[],
            evidence_excerpt=excerpt,
            first_seen_iteration=raw.get("first_seen_iteration", 0),
        ))
    return score_findings(findings, gt_path).f1


def render(ax: matplotlib.axes.Axes, case_id: str = "TEST-001") -> dict:
    apply_style()
    db_path = get_db_path(case_id)
    gt_path = GT_DIR / f"{case_id}.json"

    if not db_path.exists():
        placeholder(ax, "Panel 6 — Ablation Grid",
                    f"DB not found: {db_path}")
        return {"status": "placeholder"}

    runs = load_experiment_runs_from_db(db_path)
    if not runs:
        placeholder(ax, "Panel 6 — Ablation Grid", "No runs in DB.")
        return {"status": "placeholder"}

    labels   = []
    f1s      = []
    colors   = []
    data_out = {}

    for notes_prefix, label, color in CONFIG_DISPLAY:
        run = _find_run_by_notes(runs, notes_prefix)
        f1 = _score_run(run, db_path, gt_path) if run else 0.0
        labels.append(label)
        f1s.append(f1)
        colors.append(color)
        data_out[notes_prefix] = round(f1, 4)

    if all(f == 0.0 for f in f1s):
        placeholder(ax, "Panel 6 — Ablation Grid",
                    "No scored runs found. Check notes fields in experiment configs.")
        return {"status": "placeholder"}

    x    = np.arange(len(labels))
    bars = ax.bar(x, f1s, color=colors, width=0.5, alpha=0.85)

    for bar, f1 in zip(bars, f1s):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.01,
            f"{f1:.3f}",
            ha="center", va="bottom", fontsize=9, color=GRAY,
        )

    baseline_f1 = data_out.get("Primary baseline", 0.0)
    if baseline_f1 > 0:
        ax.axhline(baseline_f1, color=BLUE, linewidth=1,
                   linestyle="--", alpha=0.5, label="Baseline F1")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylim(0, 1.1)
    ax.set_title("Panel 6 — Ablation Grid", fontweight="bold")
    ax.set_ylabel("IOC F1 Score")
    ax.text(
        0.98, 0.02,
        "Single-seed run.\nConfidence intervals not estimated.",
        transform=ax.transAxes, ha="right", va="bottom",
        fontsize=7, color=GRAY, style="italic",
    )
    add_claim(ax, CLAIM)
    return {"status": "ok", "data": data_out}