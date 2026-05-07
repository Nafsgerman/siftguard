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
from siftguard.eval.analytics.scorer_framework import score_findings
from siftguard.eval.trace import Finding, FindingType

CLAIM = "Each feature's contribution is measured independently. Ablation reveals what actually matters."
GT_DIR  = Path(__file__).resolve().parents[4] / "tests" / "benchmark" / "ground_truth"
RES_DIR = Path(__file__).resolve().parents[4] / "experiments" / "results"

CONFIG_DISPLAY = [
    ("baseline",                    "Baseline\n(all on)",         BLUE),
    ("ablation_no_self_correction", "No self-\ncorrection",       YELLOW),
    ("ablation_no_correlation",     "No\ncorrelation",            GREEN),
    ("ablation_v1_baseline",        "v1 prompt\n(no confidence)", RED),
]


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


def _score_report(report_path: str, gt_path: Path) -> float:
    try:
        report = Path(report_path)
        if not report.exists():
            return 0.0
        text = report.read_text()
        gt = json.loads(gt_path.read_text())
        gt_iocs = gt.get("expected_iocs", [])
        findings = []
        valid_types = {t.value for t in FindingType}
        for ioc in gt_iocs:
            val = ioc["value"].lower()
            if val in text.lower():
                ftype_str = ioc["type"] if ioc["type"] in valid_types else "other"
                excerpt = (val + " " * 10)[:10]
                findings.append(Finding(
                    id=f"match-{val}",
                    type=FindingType(ftype_str),
                    value=ioc["value"],
                    confidence=0.8,
                    supporting_audit_entry_ids=[],
                    evidence_excerpt=excerpt,
                    first_seen_iteration=0,
                ))
        return score_findings(findings, gt_path).f1
    except Exception:
        return 0.0


def render(ax: matplotlib.axes.Axes, case_id: str = "TEST-001") -> dict:
    apply_style()
    gt_path = GT_DIR / f"{case_id}.json"

    if not gt_path.exists():
        placeholder(ax, "Panel 6 — Ablation Grid",
                    f"Ground truth not found: {gt_path}")
        return {"status": "placeholder"}

    labels   = []
    f1s      = []
    colors   = []
    data_out = {}

    for cfg_name, label, color in CONFIG_DISPLAY:
        result = _latest_result(cfg_name, case_id)
        if not result or not result.get("report"):
            f1 = 0.0
        else:
            f1 = _score_report(result["report"], gt_path)
        labels.append(label)
        f1s.append(f1)
        colors.append(color)
        data_out[cfg_name] = round(f1, 4)

    if all(f == 0.0 for f in f1s):
        placeholder(ax, "Panel 6 — Ablation Grid",
                    "No results found. Run experiment matrix first.")
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

    baseline_f1 = data_out.get("baseline", 0.0)
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