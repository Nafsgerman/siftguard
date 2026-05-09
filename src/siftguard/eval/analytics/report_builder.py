"""Stitches all 7 panels into composite figure + markdown report.

CLI:
    python -m siftguard.eval.analytics.report_builder
    python -m siftguard.eval.analytics.report_builder --case TEST-001
    python -m siftguard.eval.analytics.report_builder --case TEST-001 --out experiments/analysis/
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt

from siftguard.eval.analytics.style import apply_style, GRAY
from siftguard.eval.methodology import current_block
from siftguard.eval.analytics import (
    panel_1_accuracy,
    panel_2_calibration,
    panel_3_info_gain,
    panel_4_pareto,
    panel_5_hypothesis,
    panel_6_ablation,
    panel_6b_stability,
    panel_7_models,
)
from siftguard.eval.analytics.panel_8_verification import render_panel_8

PANELS = [
    panel_1_accuracy,
    panel_2_calibration,
    panel_3_info_gain,
    panel_4_pareto,
    panel_5_hypothesis,
    panel_6_ablation,
    panel_6b_stability,
    panel_7_models,
]


def build_report(case_id: str = "TEST-001", out_dir: Path | None = None) -> Path:
    apply_style()

    out_dir = out_dir or (
        Path(__file__).resolve().parents[4]
        / "experiments" / "analysis"
        / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 4, figsize=(22, 12))
    axes_flat = axes.flatten()

    fig.suptitle(
        f"SIFTGuard — Empirical Operating Characteristic Report\n"
        f"Case: {case_id}  |  Generated: "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        fontsize=14, fontweight="bold", color=GRAY, y=1.01,
    )

    all_data = {}
    _m = current_block()
    md_sections = [
        f"<!-- methodology v{_m.version} · {_m.doc} · sha256:{_m.doc_sha256[:12]}… -->",
        "",
    ]

    for i, panel_mod in enumerate(PANELS):
        ax = axes_flat[i]
        result = panel_mod.render(ax, case_id=case_id)
        all_data[f"panel_{i+1}"] = result

        # Save individual panel
        fig_ind, ax_ind = plt.subplots(figsize=(8, 5))
        panel_mod.render(ax_ind, case_id=case_id)
        ind_path = out_dir / f"panel_{i+1}_{panel_mod.__name__.split('.')[-1]}.png"
        fig_ind.savefig(ind_path, bbox_inches="tight")
        plt.close(fig_ind)

        # Markdown section
        claim = getattr(panel_mod, "CLAIM", "")
        status = result.get("status", "unknown")
        md_sections.append(
            f"## Panel {i+1}\n\n"
            f"**Claim:** {claim}\n\n"
            f"**Status:** {status}\n\n"
            f"**Data:** {json.dumps({k: v for k, v in result.items() if k != "data"}, indent=2, default=str)}\n\n"
            f"![Panel {i+1}](panel_{i+1}_{panel_mod.__name__.split('.')[-1]}.png)\n\n"
        )

    panel8 = render_panel_8([])
    all_data["panel_8"] = panel8["data"]
    md_sections.append(panel8.get("summary", ""))
    if "panel_8" in all_data and all_data["panel_8"].get("total", 0) > 0:
        all_data["hallucination_rate"] = all_data["panel_8"]["hallucination_rate"]
        all_data["verified_rate"] = all_data["panel_8"]["verified_rate"]
        all_data["unverifiable_rate"] = all_data["panel_8"]["unverifiable_rate"]

    # Hide unused axis (8th slot)
    axes_flat[7].set_visible(False)

    # Save composite
    composite_path = out_dir / "figure_full.png"
    fig.savefig(composite_path, bbox_inches="tight", dpi=200)
    plt.close(fig)

    # Save data.json
    data_path = out_dir / "data.json"
    data_path.write_text(json.dumps(all_data, indent=2, default=str))

    # Save manifest.json
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "schema_version": "1.0.0",
        "panels": [m.__name__ for m in PANELS],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Save report.md
    report_md = (
        f"# SIFTGuard Empirical Operating Characteristic Report\n\n"
        f"**Case:** {case_id}  \n"
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  \n\n"
        "## Data Quality Notes\n\n"
        "- v2 prompt parse failures fell back to v1 synthesis on several runs. "
        "These runs are included in accuracy/ablation panels and excluded from "
        "the calibration panel. The parse failure root cause (model emitting tool "
        "name strings in `supporting_audit_entry_ids` instead of integers) is "
        "documented and fixed in the v2 prompt update (commit: fix/prompt-audit-ids).\n"
        "- Single-seed runs. Confidence intervals not estimated.\n\n"
        + "\n".join(md_sections)
    )
    report_path = out_dir / "report.md"
    report_path.write_text(report_md)

    print(f"\n[analytics] Report written to {out_dir}")
    print(f"  Composite: {composite_path}")
    print(f"  Report:    {report_path}")
    print(f"  Data:      {data_path}")

    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="SIFTGuard analytics report builder")
    parser.add_argument("--case", default="TEST-001")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    out = Path(args.out) if args.out else None
    build_report(case_id=args.case, out_dir=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())