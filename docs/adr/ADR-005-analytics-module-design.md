# ADR-005: Empirical Operating Characteristic Analytics Module

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-05-07 |
| Decision Owner | Nafees A. (Solution Architect, SIFTGuard) |
| Related | ADR-001 (Eval Framework), ADR-002 (Trace Model), ADR-003 (Loop Instrumentation) |

---

## 1. Context

ADR-001 adopted an empirical evaluation framework. ADR-002 defined the Trace
data contract. ADR-003 instrumented the agent loop to populate that contract.
This ADR records the design of the analytics module that reads populated Traces
and produces the seven reporting panels.

The analytics module is the public face of the evaluation framework. It is what
judges, hiring panels, and practitioners see. Its design choices determine
whether the framework reads as rigorous science or as a dashboard with nice
charts.

---

## 2. Design Decisions

### D1 — Each panel carries a named, falsifiable claim

Every panel is paired with a one-sentence claim that the chart either supports
or refutes. The claim appears as a figure subtitle so it is visible to anyone
viewing the PNG without reading the accompanying report.

A chart without a claim is decoration. A chart with a falsifiable claim is an
argument. This module produces arguments.

### D2 — Failure panels render as explanatory placeholders

When a panel cannot be rendered (insufficient data, no confidence-tagged runs,
missing ground truth), it renders a placeholder that states why. Skipping a
panel or crashing silently hides information from the reviewer. An explanatory
placeholder shows what the framework expected, what it found, and what would
be needed to produce the panel.

### D3 — v1 fallback runs included with annotation, excluded from calibration

Runs that fell back to v1 parsing are included in accuracy, Pareto, and
ablation panels with a "v1 fallback" annotation. They are excluded from the
calibration panel because they do not emit confidence scores. Exclusion is
documented in the panel caption and the report's Data Quality section. Hiding
the fallback rate would misrepresent the v2 prompt's current reliability.

### D4 — Both composite and individual figures produced

A 4400×3000 composite figure serves as the README hero image and LinkedIn
artifact. Seven individual PNGs serve the docs site and Devpost gallery. The
cost is thirty lines of code.

### D5 — Provenance chain from trace to panel

`manifest.json` records the SHA256 hash of every Trace that contributed to
every panel. Any number in any panel can be re-derived from the same input
traces. This is the reproducibility commitment ADR-001 made, operationalised
at the figure level.

### D6 — Single-seed caveat documented, not hidden

The first matrix run used one seed per config. Confidence intervals are not
computed. Every panel that reports a point estimate carries a caption note:
"Single-seed run. Confidence intervals not estimated. See EVAL_FRAMEWORK.md
for multi-seed methodology."

Documenting the limitation is the senior move. Not documenting it is the
research-code move.

### D7 — Panel 7 (multi-model comparison) is a documented stub

Panel 7 is designed in this ADR and stubbed in code. It will be populated in
Task 8 when the multi-model matrix runs. A stub with a clear roadmap is a
stronger signal than an empty section. The stub caption reads: "Multi-model
comparison pending Task 8. Methodology: same MCP server, same ground truth,
different orchestrator client and model. See ADR-006."

---

## 3. Panel Inventory

| # | Panel | Claim | Metric |
|---|---|---|---|
| 1 | Accuracy over iterations | Self-correction improves accuracy monotonically until plateau | F1 per iteration snapshot |
| 2 | Calibration plot | Agent confidence is well-calibrated (Brier score B) | Brier score, ECE, reliability diagram |
| 3 | Info gain per tool call | Marginal gain < ε after tool call N | ΔF1 per tool call |
| 4 | Cost-accuracy Pareto | Optimal operating point is N iterations at $X | F1 vs cumulative cost USD |
| 5 | Hypothesis evolution | Agent revises beliefs in light of evidence | Hypothesis confidence over iterations |
| 6 | Ablation grid | Feature X adds Y F1 points | F1 per ablation config |
| 7 | Multi-model comparison | Stub — Task 8 deliverable | F1, cost, calibration per model |

---

## 4. Scoring Methodology

IOC matching uses token-normalised F1:
- True positive: agent finding type+value matches a ground truth IOC
  (case-insensitive, whitespace-normalised)
- False positive: agent finding not in ground truth
- False negative: ground truth IOC not in agent findings
- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2 * P * R / (P + R)

Calibration uses:
- Brier score = mean((confidence - correct)²) across all findings
- ECE = weighted mean of |confidence - accuracy| across 5 confidence bins

---

## 5. Consequences

**Positive:** Claims are falsifiable and documented. Failure modes are
visible. Provenance is cryptographic. Negative results are protected by
the framework contract.

**Negative:** Single-seed runs limit statistical claims. v2 prompt
reliability issues (parse failures falling back to v1) reduce the number
of confidence-tagged findings available for calibration. Both are
documented honestly.

---

## 6. Implementation

- `src/siftguard/eval/analytics/` — module directory
- `experiments/analysis/` — output directory
- `python -m siftguard.eval.analytics.report_builder` — CLI entry point