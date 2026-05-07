"""Panel 2 — Calibration plot.

Claim: At confidence X, the agent is correct Y% of the time.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.axes
import numpy as np

from siftguard.eval.analytics.style import (
    apply_style, add_claim, placeholder, BLUE, RED, LGRAY, GRAY
)
from siftguard.eval.analytics.load_traces import (
    load_iteration_snapshots, get_db_path, load_experiment_runs_from_db
)
from siftguard.eval.analytics.scorer_framework import score_findings
from siftguard.eval.trace import Finding, FindingType

CLAIM = "Agent confidence is well-calibrated: stated confidence matches empirical accuracy."
GT_DIR = Path(__file__).resolve().parents[4] / "tests" / "benchmark" / "ground_truth"

BINS = [0.30, 0.50, 0.70, 0.85, 0.95, 1.01]
BIN_LABELS = ["0.30–0.50", "0.50–0.70", "0.70–0.85", "0.85–0.95", "0.95–1.00"]


def _is_correct(finding: Finding, gt_iocs: list[dict]) -> bool:
    from siftguard.eval.analytics.scorer_framework import _normalise
    gt_keys = {
        (_normalise(ioc["type"]), _normalise(ioc["value"]))
        for ioc in gt_iocs
    }
    key = (finding.type.value.lower(), finding.value.lower().strip())
    return key in gt_keys


def render(ax: matplotlib.axes.Axes, case_id: str = "TEST-001") -> dict:
    apply_style()
    db_path = get_db_path(case_id)
    gt_path = GT_DIR / f"{case_id}.json"

    if not db_path.exists() or not gt_path.exists():
        placeholder(ax, "Panel 2 — Calibration Plot",
                    f"DB not found: {db_path}")
        return {"status": "placeholder"}

    gt = json.loads(gt_path.read_text())
    gt_iocs = gt.get("expected_iocs", [])

    runs = load_experiment_runs_from_db(db_path)
    confidences = []
    corrects    = []

    for run in runs:
        run_id = run["run_id"]
        config = json.loads(run.get("config_json") or "{}")
        if config.get("prompt_version", "v1") == "v1":
            continue

        snapshots = load_iteration_snapshots(db_path, run_id)
        if not snapshots:
            continue
        last_snap = snapshots[-1]
        raw_list = json.loads(last_snap.get("findings_json") or "[]")

        for raw in raw_list:
            conf = raw.get("confidence")
            if conf is None:
                continue
            try:
                ftype = FindingType(raw.get("type", "other"))
            except ValueError:
                ftype = FindingType.OTHER
            excerpt = str(raw.get("evidence_excerpt", raw.get("value", "")))[:200]
            if len(excerpt) < 10:
                excerpt = (excerpt + " " * 10)[:10]
            f = Finding(
                id=raw.get("id", "x"),
                type=ftype,
                value=str(raw.get("value", "")),
                confidence=conf,
                supporting_audit_entry_ids=[],
                evidence_excerpt=excerpt,
                first_seen_iteration=0,
            )
            confidences.append(conf)
            corrects.append(1 if _is_correct(f, gt_iocs) else 0)

    if len(confidences) < 3:
        placeholder(
            ax, "Panel 2 — Calibration Plot",
            f"Insufficient confidence-tagged findings ({len(confidences)} found).\n"
            "v2 prompt parse failures reduced calibration sample size.\n"
            "Re-run with fixed v2 prompt to populate this panel.",
        )
        return {"status": "placeholder", "n_findings": len(confidences)}

    confs = np.array(confidences)
    cors  = np.array(corrects)

    bin_means_conf = []
    bin_means_acc  = []
    bin_counts     = []

    for i in range(len(BINS) - 1):
        lo, hi = BINS[i], BINS[i + 1]
        mask = (confs >= lo) & (confs < hi)
        if mask.sum() == 0:
            continue
        bin_means_conf.append(confs[mask].mean())
        bin_means_acc.append(cors[mask].mean())
        bin_counts.append(mask.sum())

    # Perfect calibration diagonal
    ax.plot([0, 1], [0, 1], "--", color=LGRAY, linewidth=1.5,
            label="Perfect calibration", zorder=1)

    # Calibration curve
    ax.plot(bin_means_conf, bin_means_acc, "o-", color=BLUE,
            markersize=8, linewidth=2, label="SIFTGuard v2", zorder=2)

    for x, y, n in zip(bin_means_conf, bin_means_acc, bin_counts):
        ax.annotate(f"n={n}", (x, y), textcoords="offset points",
                    xytext=(5, 5), fontsize=7, color=GRAY)

    # Brier score
    brier = float(np.mean((confs - cors) ** 2))
    ece_parts = [
        abs(cm - ca) * (cnt / len(confs))
        for cm, ca, cnt in zip(bin_means_conf, bin_means_acc, bin_counts)
    ]
    ece = sum(ece_parts)

    ax.text(0.05, 0.92,
            f"Brier: {brier:.3f}  ECE: {ece:.3f}  n={len(confs)}",
            transform=ax.transAxes, fontsize=8, color=GRAY,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=LGRAY))

    ax.set_xlim(0.25, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.set_title("Panel 2 — Calibration Plot", fontweight="bold")
    ax.set_xlabel("Mean Stated Confidence")
    ax.set_ylabel("Empirical Accuracy")
    ax.legend(loc="upper left", fontsize=8)
    add_claim(ax, CLAIM)

    return {
        "status": "ok",
        "brier": brier,
        "ece": ece,
        "n_findings": len(confs),
        "bin_data": list(zip(bin_means_conf, bin_means_acc, bin_counts)),
    }