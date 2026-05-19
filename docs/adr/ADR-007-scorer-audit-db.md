# ADR-007 — Scorer Source: Report-Text Fallback vs Audit-DB Mode

**Status:** Accepted
**Date:** 2026-05-17
**Deciders:** Nafees Ahmad
**Tag at decision:** v1.19.2-task14-v2-merged-modes

---

## 1. Context

SIFTGuard's benchmark scorer (`experiments/analysis/`) currently derives F1
scores by parsing the free-text report emitted at the end of each agent run.
This approach is brittle: report formatting varies across orchestrators, regex
extraction misses structured fields, and any prompt change can silently corrupt
historical scores.

The audit DB (`audit/<case_id>.db`) is the authoritative, append-only record of
every tool call, finding, IOC, and verdict. It is the correct source of truth
for scoring — but migrating the scorer mid-hackathon would require re-running
all five orchestrators across both datasets to validate parity, a ~2-day risk.

---

## 2. Options Considered

| Option | Description | Risk |
|--------|-------------|------|
| A — Full rewrite | Replace report-text scorer with `AuditDBScorer`; re-validate all F1 numbers | Breaks Panel 1 hero numbers if parity fails; 2-day minimum |
| B — Interface stub (chosen) | Define `AuditDBScorer` interface; keep report-text scorer as active path; document migration | Zero regression risk; clean migration path post-deadline |

---

## 3. Decision

**Option B — Interface stub, defer implementation.**

The `AuditDBScorer` interface is defined now. The report-text scorer remains
the active path for all benchmark runs through June 15 submission. Full
implementation is post-deadline work.

---

## 4. Interface Specification

```python
# src/siftguard/eval/scoring/audit_db_scorer.py

from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass
class ScorerResult:
    f1: float
    precision: float
    recall: float
    tp: int
    fp: int
    fn: int
    source: str  # "audit_db" | "report_text"


class AuditDBScorer:
    """
    Score a completed investigation run from the audit DB.
    Active implementation deferred post-deadline (see ADR-007 §5).
    """

    def __init__(self, db_path: Path, ground_truth_path: Path) -> None:
        self.db_path = db_path
        self.ground_truth_path = ground_truth_path

    def score(self, case_id: str, agent_id: str) -> ScorerResult:
        raise NotImplementedError(
            "AuditDBScorer.score() is stubbed. "
            "Active scorer: siftguard.eval.scoring.report_text_scorer. "
            "See ADR-007 §5 for migration plan."
        )

    # ── Future implementation queries ──────────────────────────────────────
    # SELECT value, ioc_type FROM ioc_finding
    # WHERE case_id = ? AND agent_id = ?
    # → compare against ground_truth JSON
    # → compute TP/FP/FN → precision/recall/F1
```

---

## 5. Migration Plan (Post-Deadline)

1. Implement `AuditDBScorer.score()` using the queries above
2. Run both scorers in parallel on TEST-001 + TEST-002
3. Validate F1 parity within ±0.005 tolerance
4. Retire report-text scorer once parity is confirmed
5. Update `experiments/analysis/*/data.json` generation to use audit-DB path

---

## 6. Consequences

- **Positive:** T13 benchmark numbers remain stable through submission; no
  regression risk in the final 4 weeks.
- **Positive:** Interface is defined — future contributor can implement without
  architectural archaeology.
- **Negative:** Report-text scorer remains a fragility; format-breaking prompt
  changes could corrupt scores silently until migration completes.
- **Accepted:** Known fragility, documented, bounded by deadline constraint.
