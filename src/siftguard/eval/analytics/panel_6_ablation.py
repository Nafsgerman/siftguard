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
GT_DIR  = Path(__file__).resolve().parents[4] / "tests" / "benchmark" / "ground_truth"
RES_DIR = Path(__file__).resolve().parents[4] / "experiments" / "results"

CONFIG_DISPLAY = [
    ("Primary baseline. All features enabled.",                     "Baseline\n(all on)",         BLUE),
    ("Ablation: self_correction=false. All other features on.",     "No self-\ncorrection",       YELLOW),
    ("Ablation: correlation=false. All other features on.",         "No\ncorrelation",            GREEN),
    ("v1 baseline for prompt ablation.",                            "v1 prompt\n(no confidence)", RED),
]

NOTES_TO_CONFIG = {
    "Primary baseline. All features enabled.":                 "baseline",
    "Ablation: self_correction=false. All other features on.": "ablation_no_self_correction",
    "Ablation: correlation=false. All other features on.":     "ablation_no_correlation",
    "v1 baseline for prompt ablation.":                        "ablation_v1_baseline",
}


from siftguard.eval.analytics.scoring_helpers import (
    score_run_from_db as _score_run_db,
    score_run_from_report as _score_from_report_ioc_section,
    RES_DIR as _RES_DIR,
)


def _latest_result(config_name: str, case_id: str) -> dict | None:
    result_dir = RES_DIR / config_name / case_id
    if not result_dir.exists():
        return None
    files = sorted(result_dir.glob("result_*.json"), reverse=True)
    for f in files:
        try:
            data = json.loads(f.read_text())
            if data.get("status") == "ok":
                return data
        except Exception:
            continue
    return None


def _find_run_by_notes(runs: list[dict], notes_prefix: str) -> dict | None:
    candidates = []
    for run in runs:
        cfg = json.loads(run.get("config_json") or "{}")
        notes = cfg.get("notes", "")
        if notes.startswith(notes_prefix):
            candidates.append(run)
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.get("started_at", ""))


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
        cfg_dir = NOTES_TO_CONFIG.get(notes_prefix, "")
        run = _find_run_by_notes(runs, notes_prefix)
        if not run:
            f1 = _score_from_report_ioc_section(cfg_dir, case_id, gt_path) if cfg_dir else 0.0
        else:
            f1 = _score_run_db(run, db_path, gt_path)
            if f1 == 0.0 and cfg_dir:
                f1 = _score_from_report_ioc_section(cfg_dir, case_id, gt_path)
        labels.append(label)
        f1s.append(f1)
        colors.append(color)
        data_out[notes_prefix] = round(f1, 4)

    if all(f == 0.0 for f in f1s):
        placeholder(ax, "Panel 6 — Ablation Grid",
                    "No scored runs found.")
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

    # halluc_rate annotation — load from ablation_v2 results if available
    from siftguard.eval.ablation_runner import load_seed_results, ABLATION_DIR
    from siftguard.eval.variance import compute_variance_stats as _cvs
    HALLUC_THRESHOLD = 0.05
    for i, (bar, notes_prefix, label, color) in enumerate(zip(bars, [n for n, _, _ in CONFIG_DISPLAY], labels, colors)):
        cfg_name = NOTES_TO_CONFIG.get(notes_prefix, "")
        seed_runs = load_seed_results(cfg_name, case_id) if cfg_name else []
        halluc_vals = [r["hallucination_rate"] for r in seed_runs if r.get("hallucination_rate") is not None]
        if halluc_vals:
            h_stats = _cvs(halluc_vals)
            h_color = RED if h_stats.mean > HALLUC_THRESHOLD else GREEN
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                -0.08,
                f"halluc={h_stats.mean:.2f}",
                ha="center", va="top", fontsize=7, color=h_color,
                transform=ax.get_xaxis_transform(),
            )

    baseline_f1 = data_out.get("Primary baseline. All features enabled.", 0.0)
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