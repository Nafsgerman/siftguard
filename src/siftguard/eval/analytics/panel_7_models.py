"""Panel 7 — Multi-model comparison (stub).

Populated in Task 8 when multi-model matrix runs.
"""
from __future__ import annotations

import matplotlib.axes

from siftguard.eval.analytics.style import apply_style, placeholder

CLAIM = "Multi-model comparison: same MCP server, same ground truth, different model — vendor-risk decision matrix."


def render(ax: matplotlib.axes.Axes, case_id: str = "TEST-001") -> dict:
    apply_style()
    placeholder(
        ax,
        "Panel 7 — Multi-Model Comparison",
        "Task 8 deliverable.\n\n"
        "Methodology: same MCP server, same ground truth, same case.\n"
        "Models: Claude Sonnet, Opus, Haiku, GPT-4o, GPT-4o-mini, Gemini 2.5 Pro.\n\n"
        "See ADR-006 for multi-orchestrator design.",
    )
    return {"status": "stub", "task": "Task 8"}