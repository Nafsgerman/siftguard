"""Panel 6b — Seed Stability Chart.

Claim: headline F1 numbers are reproducible across seeds. Wide σ = got lucky.
Renders horizontal lollipops sorted by σ ascending (most stable on top).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.axes
import numpy as np

from siftguard.eval.analytics.style import (
    apply_style, add_claim, placeholder, BLUE, GREEN, YELLOW, RED, GRAY,
)
from siftguard.eval.analytics.scoring_helpers import score_seed_results
from siftguard.eval.variance import compute_variance_stats

CLAIM = "Stable means reproducible. Wide bands mean the headline number got lucky."

GT_DIR  = Path(__file__).resolve().parents[4] / "tests" / "benchmark" / "ground_truth"

# σ thresholds for visual encoding
SIGMA_WARN  = 0.02
SIGMA_BAD   = 0.05

NOTES_TO_CONFIG = {
    "Primary baseline. All features enabled.":                 "baseline",
    "Ablation: self_correction=false. All other features on.": "ablation_no_self_correction",
    "Ablation: correlation=false. All other features on.":     "ablation_no_correlation",
    "v1 baseline for prompt ablation.":                        "ablation_v1_baseline",
}

CONFIG_LABELS = {
    "baseline":                        "Baseline (all on)",
    "ablation_no_self_correction":     "No self-correction",
    "ablation_no_correlation":         "No correlation",
    "ablation_v1_baseline":            "v1 prompt",
}


def _sigma_style(sigma: float) -> tuple[str, float, str]:
    """Returns (color, linewidth, marker_text) based on σ threshold."""
    if sigma < SIGMA_WARN:
        return (GRAY, 1.5, "")
    elif sigma < SIGMA_BAD:
        return (YELLOW, 2.5, "")
    else:
        return (RED, 3.5, " ⚠")


def render(ax: matplotlib.axes.Axes, case_id: str = "TEST-001") -> dict:
    apply_style()

    try:
        from siftguard.eval.ablation_runner import load_seed_results, ABLATION_DIR
    except ImportError:
        placeholder(ax, "Panel 6b — Seed Stability", "ablation_runner not available.")
        return {"status": "placeholder"}

    gt_path = GT_DIR / f"{case_id}.json"
    if not gt_path.exists():
        placeholder(ax, "Panel 6b — Seed Stability", f"Ground truth not found: {gt_path}")
        return {"status": "placeholder"}

    rows: list[dict] = []
    for cfg_name, label in CONFIG_LABELS.items():
        seed_runs = load_seed_results(cfg_name, case_id)
        f1s = score_seed_results(seed_runs, cfg_name, case_id, gt_path)
        n = len(f1s)
        if n == 0:
            rows.append({
                "label": label, "cfg": cfg_name,
                "mean": 0.0, "std": 0.0, "n": 0,
                "ci_lower": 0.0, "ci_upper": 0.0,
            })
            continue
        stats = compute_variance_stats(f1s)
        rows.append({
            "label": label, "cfg": cfg_name,
            "mean": stats.mean, "std": stats.std, "n": stats.n,
            "ci_lower": stats.ci_lower, "ci_upper": stats.ci_upper,
        })

    if all(r["n"] == 0 for r in rows):
        placeholder(ax, "Panel 6b — Seed Stability",
                    "No seed runs found in ablation_v2/.\nRun: python -m siftguard.eval.ablation_runner --tier 1")
        return {"status": "placeholder"}

    # Sort by σ ascending (most stable on top)
    rows.sort(key=lambda r: r["std"])

    labels  = [r["label"] for r in rows]
    means   = np.array([r["mean"]     for r in rows])
    stds    = np.array([r["std"]      for r in rows])
    ci_lo   = np.array([r["ci_lower"] for r in rows])
    ci_hi   = np.array([r["ci_upper"] for r in rows])
    ns      = [r["n"] for r in rows]
    y_pos   = np.arange(len(rows))

    for i, (y, mean, std, lo, hi, n, row) in enumerate(
        zip(y_pos, means, stds, ci_lo, ci_hi, ns, rows)
    ):
        if n == 0:
            ax.scatter(0.0, y, color=GRAY, s=40, zorder=3)
            ax.text(0.02, y, "n=0 — no runs", va="center", fontsize=7, color=GRAY)
            continue

        color, lw, warn = _sigma_style(std)

        if n == 1:
            ax.scatter(mean, y, color=BLUE, s=60, zorder=3)
            ax.text(mean + 0.01, y, f"n=1", va="center", fontsize=7, color=GRAY)
            continue

        # CI band as horizontal line
        ax.hlines(y, lo, hi, colors=color, linewidth=lw, zorder=2)
        # Mean dot
        ax.scatter(mean, y, color=BLUE, s=60, zorder=3)
        # σ label at right end
        sigma_label = f"σ={std:.3f}{warn}"
        ax.text(hi + 0.005, y, sigma_label, va="center", fontsize=7,
                color=color, fontweight="bold" if std > SIGMA_BAD else "normal")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlim(max(0.0, float(means[means > 0].min()) - 0.15) if any(means > 0) else 0.0, 1.05)
    ax.set_xlabel("IOC F1 Score", fontsize=9)
    ax.set_title("Panel 6b — Seed Stability (σ error bands)", fontweight="bold")
    ax.axvline(float(means.max()), color=BLUE, linewidth=1, linestyle="--",
               alpha=0.4, label="Best mean F1")
    ax.text(0.98, 0.02,
            f"n_seeds per config shown at right.\nSorted by σ (stable → unstable).",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=7, color=GRAY, style="italic")
    add_claim(ax, CLAIM)

    return {
        "status": "ok",
        "data": {r["cfg"]: {"mean": r["mean"], "std": r["std"], "n": r["n"]} for r in rows},
    }