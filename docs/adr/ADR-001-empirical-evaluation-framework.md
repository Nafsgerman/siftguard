# ADR-001: Adopt an Empirical Evaluation Framework as a First-Class Component

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-05-06 |
| Decision Owner | Nafees A. (Solution Architect, SIFTGuard) |
| Stakeholders | DFIR practitioners, enterprise security leadership, hackathon judges, future contributors |
| Supersedes | — |
| Superseded By | — |
| Related | ADR-005 (Allowlist as primary defense), ADR-007 (Audit trail design for legal admissibility) |

---

## 1. Context

SIFTGuard is an autonomous incident-response agent. It runs on the SANS SIFT
Workstation, calls forensic tools through a typed MCP server, and produces
court-defensible incident reports without human intervention.

A non-trivial share of the autonomous-agent literature, and a much larger share
of vendor marketing, treats agent quality as a narrative property rather than a
measurable one. Agents are described as "self-correcting", "robust",
"high-accuracy", or "trustworthy" without a defined methodology that would let
a customer, a contributor, or a contracting officer verify those claims on
their own data.

For a system that operates inside an active forensic investigation — where
findings may be cited in disciplinary proceedings, regulatory submissions, or
court — narrative quality is not sufficient. The system must be measurable, the
methodology must be reproducible, and the methodology must generalise beyond
this one project so that any agent making similar claims can be evaluated on
the same axes.

This ADR records the decision to build that evaluation methodology as a
first-class, agent-agnostic component of SIFTGuard, rather than as a
late-stage benchmark or a marketing artefact.

---

## 2. Problem Statement

Three concrete problems motivate this decision.

**(1) Unfalsifiable claims weaken adoption.** A claim such as "SIFTGuard is
self-correcting" is not actionable for a security buyer. They cannot tell
whether self-correction adds value, costs tokens for no gain, or actively
hurts accuracy on certain case types. Without an evaluation framework that
isolates the contribution of self-correction, the feature is asserted, not
demonstrated.

**(2) Hallucination risk is asymmetric in DFIR.** A false negative in a
forensic context (missed indicator) is recoverable. A false positive
(hallucinated indicator) attached to an investigation can survive into a
report, drive a containment decision, and damage a stakeholder relationship
or a legal position. Detection of hallucination must therefore be
mechanical, not advisory.

**(3) The DFIR community lacks a shared evaluation harness for autonomous
agents.** The hackathon brief explicitly notes that the community needs a
benchmark. Existing tool-level benchmarks (Volatility plugins, RegRipper
parsers) measure individual tools; they do not measure agentic behaviour —
sequencing, self-correction, hypothesis revision, calibration of confidence,
or cost-accuracy trade-offs. A new agentic system entering the field has no
shared reference points to be measured against.

If SIFTGuard ships without addressing these three problems, it competes on
narrative. If it ships with the methodology to address them, it raises the
floor for every subsequent agent in the field — including agents that are not
SIFTGuard.

---

## 3. Decision

We adopt an Empirical Operating Characteristic (EOC) framework as a
first-class component of SIFTGuard, with the following non-negotiable
properties:

1. **Agent-agnostic from line one.** The framework consumes a `Trace` data
   structure, not SIFTGuard internals. Any agent — a competing custom MCP
   server, a multi-agent orchestrator, an agentic IDE workflow, a future
   commercial product — can implement a `to_trace()` adapter and be evaluated
   on the same axes.

2. **Methodology is a public artefact.** `EVAL_FRAMEWORK.md` documents
   scoring rules, ground-truth schema, calibration methodology, ablation
   conventions, and reproducibility requirements. The methodology is
   versioned in git and tagged with the release.

3. **Ground truth is a separately versioned dataset.** Ground truth lives
   in a `benchmark-data` directory with its own semantic version and schema.
   A future contributor can submit cases, propose edits, and trace
   methodology changes back to specific commits.

4. **Reports are reproducible.** Every experiment run is identified by a
   `run_id`, parameterised by a config dictionary, executed at fixed model
   temperature and seed, and produces a deterministic output triple:
   `trace.json`, `panels.png`, `report.md`. A reviewer can rerun any
   reported figure from the repo.

5. **Negative results are reported honestly.** If the agent is overconfident
   on a calibration plot, the framework reports it. If self-correction
   degrades accuracy on certain cases, the framework reports it. Suppression
   of unfavourable results breaks the contract of this decision.

6. **The framework runs in CI.** Eval-framework regressions are detected
   automatically. A pull request that degrades accuracy, calibration, or
   cost-efficiency below documented thresholds blocks merge.

The framework produces seven reporting panels:

| # | Panel | Question it answers |
|---|---|---|
| 1 | Accuracy over iterations | Does the agent actually improve as it self-corrects? |
| 2 | Calibration plot | Is the agent's stated confidence trustworthy? |
| 3 | Information gain per tool call | Is the next iteration worth the tokens? |
| 4 | Cost-accuracy Pareto frontier | What is the optimal operating point for a given budget? |
| 5 | Hypothesis evolution timeline | Does the agent revise beliefs in light of evidence? |
| 6 | Ablation grid | What does each feature actually contribute? |
| 7 | Comparative panel | How does this agent compare to others on the same case data? |

---

## 4. Options Considered

### Option A — No evaluation framework

Ship the system, demonstrate it on one case, rely on narrative quality.

*Why rejected.* This is the failure mode the framework is designed to
address. It would force every prospective adopter to build their own
evaluation harness, and would prevent contract-relevant claims from being
defensible.

### Option B — Single-metric benchmark (overall accuracy %)

Score the final report against ground truth and publish a single number per
case.

*Why rejected.* A single number conceals the dynamics that matter most in
agentic systems: where in the loop the agent fails, whether self-correction
helps or hurts, whether the agent is calibrated, whether it spends tokens
proportionally to accuracy gain. A single number is also trivial to
overfit on, both intentionally and unintentionally.

### Option C — Tool-level benchmark (per-tool precision/recall)

Evaluate each forensic tool's wrapping in isolation.

*Why rejected.* The hard problems in autonomous DFIR are not at the tool
level — they are at the orchestration, sequencing, and reasoning level. A
tool-level benchmark would score the easy part of the system and ignore
the part that determines whether the agent is actually useful.

### Option D — Internal "feels right" QA

Run cases manually, eyeball the outputs, ship.

*Why rejected.* Not reproducible, not auditable, not extensible to
contributors, not legible to enterprise buyers, not defensible in a
contract or compliance review.

### Option E (chosen) — Empirical Operating Characteristic framework

A multi-panel, agent-agnostic, version-controlled evaluation methodology
with reproducibility, calibration, and ablation as load-bearing components.

*Why chosen.* Resolves all three motivating problems, generalises to other
agents, runs in CI, produces artefacts that survive enterprise procurement
review, and elevates the DFIR community's evaluation floor.

### D5 — Cross-case generalization claims require validated cross-case data

TEST-004 and TEST-005 cache warm-up completed but the ground truth files
shipped with those cases were authored against a different image set —
the expected IOCs do not exist in the memory images we have. Scored runs
return F1 of 0.074 and 0.000 respectively, but those numbers reflect ground
truth mismatch, not agent failure. They are not safe to cite as
generalization evidence.

The decision: the headline does not claim cross-case generalization.
It claims 0.909 IOC F1 (σ = 0.000) on TEST-001 and discloses the
TEST-004/005 ground-truth gap as the next research-grade prerequisite —
in `LIMITATIONS.md` and on the roadmap, not as a footnote.

*Rejected alternative 1:* Cite the 0.074 / 0.000 numbers as generalization
results. This would be the failure mode the framework was built to expose:
publishing scored outputs without first validating that the scorer's inputs
are correct. A near-zero F1 against wrong ground truth tells you nothing
about the agent.

*Rejected alternative 2:* Treat TEST-001 as the entire reported scope and
omit TEST-004/005 entirely. Honest about what we have, but lossy — readers
should know cross-case data was attempted, what blocked it, and what
unblocking it requires. The visible gap is part of the empirical record.

---

## 5. Consequences

### Positive consequences

- **Claims become falsifiable.** Every assertion in the README about
  accuracy, self-correction, calibration, or cost is grounded in a
  reproducible figure.
- **Contributors have a contract.** A new feature must demonstrate its
  contribution via the ablation grid; a regression is detected automatically.
- **Buyers have a decision tool.** The cost-accuracy Pareto frontier and
  the multi-model comparison (see ADR-006) directly inform deployment
  decisions for a customer SOC.
- **The methodology has standalone value.** Other DFIR-agent submissions
  can adopt the framework and report on the same axes, raising the
  community's evaluation floor.
- **Negative results are protected.** The framework's contract is to
  publish them; this protects the project from drifting into vendor-style
  narrative quality over time.

### Negative consequences

- **Up-front cost.** The framework is approximately one focused work-week
  to build, plus API budget for the experiment matrix. This is significant
  relative to a hackathon timeline.
- **Schema migration cost.** The audit-trail schema must be extended
  before instrumentation. Backfill of historical runs is not attempted;
  pre-migration data is treated as exploratory.
- **Discipline cost on every future change.** New features must include
  an ablation slot and an updated panel; this slows iteration in exchange
  for permanent legibility.
- **Risk of unfavourable headline numbers.** The framework will surface
  weaknesses (e.g. overconfidence at high stated confidence). The
  contract requires reporting these. This is a feature, not a bug, but
  it must be acknowledged.

### Risks

- *Methodology drift.* The framework itself can be adjusted to flatter
  the agent. Mitigation: methodology is versioned, changes require an
  ADR amendment, ground truth is separately versioned.
- *Reproducibility breakage.* Model behaviour at fixed temperature is
  not perfectly deterministic. Mitigation: seeded repeated runs for
  baseline ablations, confidence intervals reported on key panels.
- *Ground-truth disputes.* A contributor may dispute a labelled IOC.
  Mitigation: ground truth lives in a separate dataset with a
  proposal-and-review process documented in `EVAL_FRAMEWORK.md`.

---

## 6. Compliance and Governance Implications

This framework is the load-bearing artefact for the following compliance
and governance positions taken elsewhere in the project:

- The accuracy claims in the README, in `THREAT_MODEL.md`, and in
  customer-facing documentation are all backed by experiment runs in
  `experiments/`.
- The "evidence integrity" claim (no spoliation) is enforced
  architecturally (ADR-005) and verified empirically through the
  spoliation test suite, which runs in the same CI pipeline as the
  framework.
- The "no hallucinations" claim is operationalised as a measurable
  *hallucination-rejection rate*, computed by `verify_finding()` on every
  experiment run. The rate is reported, not asserted.
- For regulated deployments (financial services, healthcare, public
  sector), the framework provides the reproducibility evidence required
  for model-risk-management documentation under frameworks such as
  SR 11-7 and the EU AI Act's high-risk-system obligations.

---

## 7. Implementation Plan

The following items are tracked in the master task plan and must be
delivered together for this ADR to be considered implemented:

1. Audit-trail schema migration adding token-cost, confidence, and
   correction-event columns; new tables for iteration snapshots,
   hypothesis events, and experiment runs.
2. `Trace` Pydantic model and serialiser, designed for cross-agent
   adoption.
3. Structured-confidence rewrite of `SYSTEM_PROMPT` so that confidence
   scores are first-class outputs of the agent, not parsed from prose.
4. Instrumentation of `agent/loop.py` to populate the new schema on
   every iteration boundary.
5. Experiment runner CLI (`python -m experiments.run --config <name>`)
   parameterised by config dictionaries.
6. `analytics/operating_characteristic.py` implementing the seven
   reporting panels.
7. `EVAL_FRAMEWORK.md` documenting methodology, ground-truth schema,
   and the contributor contract.
8. CI integration: the framework runs on every push to main; thresholds
   are enforced.
9. Embedding of hero figures in `README.md` and the dashboard's
   Empirical Evidence panel.
10. Tagged release `v1.1.0-eval-framework` once the above are merged.

---

## 8. Open Questions Deferred to Future ADRs

- Cross-agent calibration comparison methodology (when agents from
  different vendors report confidence on different scales) — deferred
  to a future ADR once the multi-model matrix in ADR-006 is stable.
- Contribution governance for community-submitted ground-truth cases
  — deferred to a future ADR once the framework is in external use.
- Statistical significance reporting (currently confidence intervals
  via seeded repeats; bootstrap reporting deferred).

---

## 9. References

- SANS FIND EVIL hackathon brief, project idea #5 ("Accuracy Benchmarking
  Framework"), 2026.
- Federal Reserve Board, *SR 11-7: Guidance on Model Risk Management*, 2011.
- European Union, *Artificial Intelligence Act*, high-risk-systems
  obligations on logging and reproducibility, 2024.
- Anthropic, *Claude Opus 4.7 system card*, methodology references on
  evaluation discipline and calibration reporting.
- Anthropic, *GTG-1002 incident report*, November 2025, motivating the
  defensive-side urgency for measurable, not narrative, agent quality.
