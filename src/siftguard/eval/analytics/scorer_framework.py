"""Score a Trace against ground truth — token-normalised F1.

ADR: docs/adr/ADR-005-analytics-module-design.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
import json

from siftguard.eval.trace import Trace, Finding


def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


@dataclass
class ScoreResult:
    precision: float = 0.0
    recall:    float = 0.0
    f1:        float = 0.0
    tp:        int   = 0
    fp:        int   = 0
    fn:        int   = 0
    matched_iocs:  list[str] = field(default_factory=list)
    missed_iocs:   list[str] = field(default_factory=list)
    false_pos:     list[str] = field(default_factory=list)


def score_findings(
    findings: list[Finding],
    ground_truth_path: str | Path,
) -> ScoreResult:
    gt = json.loads(Path(ground_truth_path).read_text())
    gt_iocs: list[dict] = gt.get("expected_iocs", [])

    gt_keys = {
        (_normalise(ioc["type"]), _normalise(ioc["value"]))
        for ioc in gt_iocs
    }

    pred_keys = {
        (_normalise(f.type.value), _normalise(f.value))
        for f in findings
    }

    tp_keys = pred_keys & gt_keys
    fp_keys = pred_keys - gt_keys
    fn_keys = gt_keys - pred_keys

    tp = len(tp_keys)
    fp = len(fp_keys)
    fn = len(fn_keys)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0 else 0.0
    )

    return ScoreResult(
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        tp=tp, fp=fp, fn=fn,
        matched_iocs=[f"{t}:{v}" for t, v in tp_keys],
        missed_iocs=[f"{t}:{v}" for t, v in fn_keys],
        false_pos=[f"{t}:{v}" for t, v in fp_keys],
    )


def score_trace(trace: Trace, ground_truth_path: str | Path) -> ScoreResult:
    return score_findings(list(trace.findings), ground_truth_path)


def score_at_iteration(
    trace: Trace,
    iteration: int,
    ground_truth_path: str | Path,
) -> ScoreResult:
    """Score only the findings first seen at or before a given iteration."""
    findings = [
        f for f in trace.findings
        if f.first_seen_iteration <= iteration
    ]
    return score_findings(findings, ground_truth_path)