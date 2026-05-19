# SIFTGuard Empirical Evaluation Framework — Methodology

**Methodology Version:** 1.0.0
**Last Updated:** 2026-05-07
**Status:** Stable
**Codebase Compatibility:** ≥ v1.3.0-analytics-complete

---

## 0. What this document is for

This is the methodology contract for SIFTGuard's empirical evaluation
framework. It tells you:

- How findings are scored against ground truth, exactly
- What the calibration metrics mean and how they are computed
- Which runs are included in which panels and why
- What this framework does **not** measure
- Which failure modes are documented and which are not
- The governance contract for changing any of the above

If you want to reproduce a number in any analytics panel, this document
plus the data files in `experiments/analysis/` are sufficient. If they
are not, that is a defect in this document, and a fix should be raised.

This is not the place to learn how to use SIFTGuard. See the README.
This is not the place to read architectural decisions. See `docs/adr/`.
This is the place to audit the eval framework's truth-claims.

---

## 1. Scope and non-goals

### What the framework measures

- IOC-level finding accuracy (precision, recall, F1) against versioned ground truth
- Calibration of agent-stated confidence against empirical correctness (Brier, ECE)
- Per-iteration accuracy trajectory and information gain per tool call
- Cost-accuracy operating characteristics across configuration variants
- Hypothesis evolution across the agent loop

### What the framework does not measure

The following are explicit non-goals at Methodology v1.0.0. Future
versions may extend scope; this version does not.

- **Forensic-tool-level accuracy.** Volatility's accuracy is treated as
  ground truth at the tool-output layer. We are evaluating the agent
  loop, not the underlying analysis tools.
- **End-to-end deployment latency.** Wall-clock numbers in cost-Pareto
  panels measure agent reasoning latency on a warm tool cache. They are
  not deployment SLA estimates.
- **User experience or analyst workflow integration.** Out of scope.
- **Regulatory or compliance certification.** This framework is not a
  basis for SOC 2, ISO 27001, or EU AI Act conformity assessment. It is
  internal engineering rigour, intended to inform — not replace — formal
  conformity work.
- **Multi-language IOCs or non-Windows artifacts.** Scoring assumes
  Windows artifact naming conventions and ASCII-only IOC values.
- **Adversarial robustness.** No prompt-injection or evidence-poisoning
  evaluation is performed at v1.0.0.

### Audience

This framework is designed for three audiences in this order:

1. **Engineers extending SIFTGuard** (the primary audience)
2. **Security reviewers** auditing claims before deployment
3. **Hackathon judges and hiring reviewers** evaluating the work

If a presentation choice helps the third audience but misleads the first,
the first audience wins.

---

## 2. Methodology versioning

**Every result produced by this framework is annotated with the
methodology version under which it was produced.** Methodology version
1.0.0 is defined entirely by this document.

A methodology version bump is required when **any** of the following
changes:

- The scoring algorithm in `siftguard/eval/analytics/scorer_framework.py`
- The set of fields contributing to F1 calculation
- The calibration binning scheme or metric definitions
- The ablation panel's run-selection rules
- The Pareto frontier construction algorithm
- The ground truth schema in `tests/benchmark/ground_truth/*.json`

Code changes that do **not** require a methodology version bump:

- Bug fixes that bring code into line with this document
- Performance optimisations that produce identical numerical output
- New panels that report new metrics (the new metric is added; existing
  metrics are unchanged)
- New ground truth files for new cases (existing cases unchanged)

When a methodology version bump occurs, prior results are not invalidated.
They remain valid under their original methodology version, and reports
from before and after the bump are not directly comparable on any metric
whose definition changed. The change log in this document records what
changed and why.

This versioning commitment is the framework's primary credibility
contract. Without it, "we improved by 3 F1 points" can be the result of
a scoring rule change rather than an agent improvement, and no reader can
distinguish the two.

---

## 3. Ground truth

### Schema

Each test case has a JSON file at `tests/benchmark/ground_truth/{CASE_ID}.json`:

```json
{
"case_id": "TEST-001",
"description": "...",
"threat_type": "apt_c2",
"expected_iocs": [
{"type": "process", "value": "license_ctrl", "confidence": "high"}
],
"expected_persistence": true,
"expected_lateral_movement": false,
"expected_timestomp": false,
"expected_code_injection": false,
"expected_verdict_keywords": ["license_ctrl", "172.16.4.10", "c2"],
"required_sections": ["Executive Summary", "..."]
}

### IOC types

Valid IOC types for v1.0.0:

- `process` — process name (executable basename)
- `ip` — IPv4 address (with or without port suffix)
- `port` — TCP/UDP port number as string
- `technique` — MITRE ATT&CK keyword (`c2`, `persist`, `lateral`)
- `file` — file name or path
- `registry_key` — registry key path
- `persistence` — persistence mechanism keyword
- `other` — fallback for typed values not covered above

### IOC value normalisation

When scoring, IOC values are compared after the following normalisation:

1. Lowercase
2. Whitespace collapsed to a single space
3. Leading and trailing whitespace stripped

A finding matches a ground-truth IOC when (a) types match exactly after
normalisation and (b) **either** the finding value contains the ground-truth
value as a substring **or** the ground-truth value contains the finding
value as a substring.

This bidirectional substring match is intentional. It accommodates two
real-world phenomena:

- The model emits process names with truncated extensions (`license_ctrl.e`
  instead of `license_ctrl`)
- The model emits IP addresses with port suffixes (`172.16.4.10:8080` vs
  `172.16.4.10`)

The cost of permissive matching is that two distinct ground-truth IOCs
that are substrings of each other could collide. This is documented as a
known limitation: ground truth files must not contain IOCs of the same
type where one value is a substring of another.

### Ground truth versioning

Each ground truth file carries an implicit version (the file's git SHA).
When ground truth changes for a case, runs scored against the previous
version are not directly comparable to runs scored against the new
version. The `data.json` produced by the analytics module records the
ground truth file SHA for each panel.

### Ground truth contributor governance

Adding or modifying a ground truth file requires:

1. Documented evidence justifying each IOC (Volatility output excerpt,
   public threat intel reference, or original case documentation)
2. Confidence labelling (`high`, `medium`, `low`) per IOC
3. PR review by an evaluator who has not produced agent code that runs
   against this case (avoids self-marking)
4. Methodology version annotation in the file's commit message

Ground truth is the framework's foundation. Sloppy ground truth makes
every metric meaningless.

---

## 4. Scoring methodology

### IOC F1 score

For a set of agent findings *F* and a set of ground-truth IOCs *G*:

- True Positive (TP): a finding *f ∈ F* matches some IOC *g ∈ G* under
  the type-equal + bidirectional-substring rule (Section 3)
- False Positive (FP): a finding *f ∈ F* with no matching *g ∈ G*
- False Negative (FN): an IOC *g ∈ G* with no matching *f ∈ F*

Precision = TP / (TP + FP)    if (TP + FP) > 0, else 0.0
Recall    = TP / (TP + FN)    if (TP + FN) > 0, else 0.0
F1        = 2 * P * R / (P + R)    if (P + R) > 0, else 0.0

Findings with the same `(type, value)` after normalisation are
deduplicated before scoring. A duplicated finding does not contribute
two TPs.

### Per-iteration scoring

Panel 1 (accuracy over iterations) scores the cumulative findings up to
and including each iteration. The findings list is built from
`iteration_snapshot` rows in the audit DB, ordered by iteration index.

A finding's `first_seen_iteration` is the lowest iteration in which the
agent emitted that `(type, value)` tuple.

### Methodology asymmetry: v1 vs v2 runs

The v1 agent loop does not produce structured `iteration_snapshot` rows.
For runs scored against the v1 prompt, the analytics module falls back to
**IOC section text matching**:

1. Extract the markdown section under `## Indicators of Compromise` from
   the run's report file
2. For each ground-truth IOC, test whether its lowercase value appears
   as a substring within that section
3. Construct a synthetic findings list from matched IOCs
4. Score the synthetic findings list using the same F1 formula

This is **not directly comparable** to v2 scoring. v2 scoring evaluates
the agent's structured findings emitted into the JSON contract. v1
scoring evaluates whether the right strings appear in the report.

The Panel 6 ablation chart annotates the v1 bar with this caveat in the
caption. Direct numerical comparisons across the v1/v2 prompt versions
are explicitly disclaimed.

### Why F1, not just accuracy

A pure-recall agent that emits every plausible IOC scores high on
recall and useless on precision. A pure-precision agent that emits only
its most confident finding scores high on precision and misses real
threats. F1 penalises both failure modes symmetrically. Until we have
operating-context-specific cost asymmetry (e.g. an IR team that values
recall over precision 4:1), F1 is the honest default.

---

## 5. Calibration

### Reliability diagram

Findings are binned by stated `confidence` into 5 bins:

| Bin | Range |
|-----|-------|
| 1 | [0.30, 0.50) |
| 2 | [0.50, 0.70) |
| 3 | [0.70, 0.85) |
| 4 | [0.85, 0.95) |
| 5 | [0.95, 1.00] |

For each bin we compute:

- Mean stated confidence within the bin
- Empirical accuracy: fraction of findings in the bin that match a
  ground-truth IOC under the Section 4 rule
- Bin sample count

These are plotted against the diagonal *y = x* (perfect calibration).

### Brier score

Brier = (1/N) * Σ (confidence_i - correct_i)²

Where `correct_i` is 1 if finding *i* matches a ground-truth IOC, 0
otherwise. Lower is better. Range [0, 1].

### Expected Calibration Error (ECE)

ECE = Σ (n_b / N) * |mean_confidence_b - empirical_accuracy_b|

Where the sum is over non-empty bins, *n_b* is bin sample count, *N* is
total findings. Lower is better.

### Calibration sample inclusion rules

- Only v2 runs contribute to the calibration panel. v1 runs do not emit
  confidence scores and are excluded by construction.
- v2 runs that fell back to v1 synthesis at any iteration are excluded
  from calibration; their findings have no associated confidence.
- Findings with `confidence = None` are excluded.
- Findings with `confidence < 0.30` are excluded (the prompt's reporting
  floor; values below 0.30 are explicitly designated as noise).

### Single-seed caveat

At Methodology v1.0.0, runs use a single seed. Calibration error bars
are not estimated. A 0.05 ECE on this evaluation should not be
interpreted as a 0.05 ± 0.005 estimate; it is a single measurement
with unknown variance.

Multi-seed runs are committed for Methodology v1.1.0.

---

## 6. Ablation methodology

### Ablation configurations

The Panel 6 ablation grid compares four canonical configurations defined
in `experiments/configs/`:

| Config | Notes prefix | Self-correction | Correlation | Prompt |
|--------|--------------|-----------------|-------------|--------|
| baseline | "Primary baseline. All features enabled." | true | true | v2 |
| no_self_correction | "Ablation: self_correction=false. ..." | false | true | v2 |
| no_correlation | "Ablation: correlation=false. ..." | true | false | v2 |
| v1_baseline | "v1 baseline for prompt ablation." | true | true | v1 |

### Run selection

For each ablation cell, the analytics module selects the **most recent
successful run** matching the configuration's `notes` field exactly. The
match is on the full notes string, not a substring, to prevent collisions
between configurations whose notes share prefixes.

When multiple runs of the same configuration exist (e.g. matrix re-runs),
only the latest is included. The framework does not currently average
across re-runs at v1.0.0; this is a Methodology v1.1.0 commitment.

### Effect attribution

The framework reports point-estimate F1 differences between cells. It
does **not** claim that observed differences are statistically
significant at v1.0.0. Single-seed runs preclude significance testing.

When a hiring panel or judge asks "does self-correction add F1 points?",
the v1.0.0 honest answer is: "Not measurable to statistical significance
in the current single-seed setup. Multi-seed evaluation is committed for
v1.1.0. The point estimate at v1.0.0 was X."

This honesty is a feature, not a bug.

---

## 7. Cost-accuracy Pareto methodology

### Cost computation

Run cost in USD is computed from token counts emitted by the Anthropic
API per the price table in `siftguard/agent/instrumentation.py`. The
table is updated when prices change; historical reports retain the
prices in effect at the time of the run via `manifest.json`.

Tool execution time is excluded from cost. Volatility runs against a
warm cache produce zero-token tool calls; the dominant cost is LLM
reasoning tokens.

### Pareto frontier construction

A run is on the Pareto frontier if no other run has both:

- Lower total cost AND
- Greater or equal F1

OR

- Lower or equal total cost AND
- Greater F1

Frontier points are marked with star markers; non-frontier points with
circles. The Pareto frontier is recomputed for each panel render; it is
not cached.

### Operating point recommendation

The framework does not recommend a deployment operating point at v1.0.0.
Frontier visualisation is informational. A deployment recommendation
requires multi-case generalisation (committed v1.1.0) and operational
SLA constraints not in scope here.

---

## 8. Reproducibility

### Provenance chain

Every analytics panel is reproducible from:

- The audit DB SQLite file
- The ground truth JSON files
- The methodology version of the framework
- The codebase at the analytics module's git SHA

The `manifest.json` produced alongside each report records:

- Generated timestamp (UTC)
- Case ID
- Methodology version
- Schema version of the Trace data model
- Git SHA of the analytics module
- Ground truth file SHA per case
- Run IDs that contributed to each panel

To re-derive any number in any panel:

1. Check out the recorded git SHA
2. Restore the audit DB to its state at the recorded timestamp
3. Run `python -m siftguard.eval.analytics.report_builder --case {ID}`
4. Compare against the original `data.json`

If the numbers differ, either provenance is broken or the framework has
a non-determinism bug. Both are reportable defects.

### Determinism guarantees

The analytics module is deterministic given the same input data. The
agent loop is **not** deterministic — the LLM produces different output
across runs even with `seed=42`. This is why methodology v1.0.0 reports
single-seed point estimates and commits to multi-seed in v1.1.0.

### Data retention

Audit DBs are retained per case at `/cases/{CASE_ID}/siftguard/audit/`.
Result JSON files are retained at `experiments/results/{config}/{CASE_ID}/`.
Both are versioned in git when small enough; larger artifacts are
referenced by SHA from `manifest.json`.

---

## 9. Failure modes

The framework's known failure modes at v1.0.0:

### v2 prompt parse failures

The v2 prompt occasionally produces JSON that fails schema validation.
On parse failure, the loop retries once; on second failure, it falls
back to a v1-style synthesis. The fallback rate per matrix run is
recorded in the report's Data Quality section.

When a v2 run falls back, its findings are still scored, but its
confidence scores are absent and the run is excluded from calibration.

### Single-seed variance

All single-seed point estimates carry unknown variance. Reported
F1 differences below ~0.05 should be interpreted with caution.

### Cache effects on cost

Pre-warmed Volatility caches produce near-zero tool execution time.
Reported costs are therefore LLM-token costs only. A cold-start run
would incur additional minutes per Volatility tool call. This is a
property of the evaluation environment, not of SIFTGuard's deployment
characteristics.

### v1/v2 scoring asymmetry

Documented in Section 4. v1 ablation bar values are not directly
comparable to v2 ablation bar values.

### Substring-match collision risk

Documented in Section 3. Mitigated by ground truth governance.

---

## 10. Roadmap commitments

These commitments will land in the listed methodology version.

### Methodology v1.1.0

- Multi-seed runs (n=3 minimum) per matrix configuration
- Confidence intervals via bootstrap on the seed distribution
- Multi-case panels: TEST-004 and TEST-005 generalisation
- Statistical significance reporting on ablation deltas

### Methodology v1.2.0

- Multi-orchestrator and multi-model panels (Panel 7 populated)
- Cross-model calibration comparison
- Vendor-risk decision matrix backed by data

### Methodology v2.0.0 (forecast)

- Adversarial robustness eval (prompt injection, evidence poisoning)
- Real disk + memory paired correlation evaluation
- Operator-context-weighted F1 (recall-favoured for IR triage,
  precision-favoured for compliance reporting)

Roadmap commitments are not contracts but they are public. If a v1.1.0
commitment slips, the slip is documented in this section.

---

## 11. Governance

### Change classifications

| Change type | Authority required | Methodology bump? |
|-------------|-------------------|-------------------|
| Add panel reporting new metric | Maintainer | No |
| Add new test case | Maintainer + ground truth review | No |
| Change scoring rule | Maintainer + open RFC | Yes (semver minor) |
| Change F1 to alternative metric | Maintainer + open RFC | Yes (semver major) |
| Change ground truth on existing case | Maintainer + ground truth review | No (file SHA changes) |
| Add new IOC type | Maintainer | Yes (semver minor) |

### Contribution process

1. Read this document end-to-end
2. Read the relevant ADR(s) in `docs/adr/`
3. Open an RFC issue for any change requiring a methodology bump
4. PR with:
   - Code change
   - Documentation update (this file + ADR if architectural)
   - Test demonstrating the change works
   - Methodology version bump if required

### Maintainer

At Methodology v1.0.0, sole maintainer is the SIFTGuard project lead. As
the framework matures, this role may be split (e.g. a separate Ground
Truth Maintainer). Any such split will be reflected in this section.

---

## 12. Change log

### Methodology v1.0.0 — 2026-05-07

Initial release. Defines:

- IOC F1 scoring with bidirectional substring matching
- 5-bin calibration with Brier and ECE
- 4-cell ablation matrix
- Single-seed methodology with documented variance limitations
- v1/v2 scoring asymmetry as documented behaviour, not a defect
- Methodology versioning as the framework's primary credibility commitment

---

## 13. References

- `docs/adr/ADR-001-empirical-evaluation-framework.md` — Framework adoption
- `docs/adr/ADR-002-trace-data-model.md` — Trace data contract
- `docs/adr/ADR-003-loop-instrumentation.md` — Loop instrumentation
- `docs/adr/ADR-005-analytics-module-design.md` — Analytics module

External references:

- SR 11-7 (Federal Reserve Guidance on Model Risk Management)
- EU AI Act, Articles 9 and 15 (high-risk AI system requirements)
- Brier (1950), "Verification of forecasts expressed in terms of
  probability," *Monthly Weather Review*, 78(1)
- Naeini et al. (2015), "Obtaining well-calibrated probabilities using
  Bayesian binning," *AAAI*

---

*This document is the methodology contract for SIFTGuard's eval
framework. All claims made by the framework are claims under this
methodology. If you find a result inconsistent with this document, the
result is wrong, the document is wrong, or both. Either way it is a
defect, please raise it.*
