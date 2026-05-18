"""SIFTGuard empirical operating characteristic analytics module.

ADR: docs/adr/ADR-005-analytics-module-design.md
"""

from siftguard.eval.analytics import (  # noqa: F401
    panel_1_accuracy,
    panel_2_calibration,
    panel_3_info_gain,
    panel_4_pareto,
    panel_5_hypothesis,
    panel_6_ablation,
    panel_6b_stability,
    panel_7_models,
)
