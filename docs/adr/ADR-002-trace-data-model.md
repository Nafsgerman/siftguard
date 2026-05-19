# ADR-002: Trace Data Model for Agent-Agnostic Evaluation

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-05-06 |
| Decision Owner | Nafees A. (Solution Architect, SIFTGuard) |
| Related | ADR-001 (Empirical Evaluation Framework) |

---

## 1. Context

ADR-001 adopted an agent-agnostic empirical evaluation framework. That
decision requires a shared data contract: a portable, version-stamped,
hashable record of a completed agent run that any agent can emit and the
framework can score — without reading agent internals.

This ADR records the design decisions for that contract: the `Trace` model.

---

## 2. Design Decisions and Rationale

### D1 — Confidence absence over synthetic data

Agents that do not emit structured confidence scores (e.g. Protocol SIFT
baseline) produce `confidence=None` on findings and verdicts. The framework
excludes these from calibration panels and reports the exclusion explicitly.

*Rejected alternative:* Adapters assign synthetic confidence (e.g. uniform
0.5). This would pollute calibration plots and undermine the framework's
contract of honesty. A misleading calibration panel is worse than no panel.

### D2 — Canonical finding with iteration history separate

When an agent reports the same IOC in multiple iterations, the `Trace`
carries one canonical `Finding` with `first_seen_iteration` set to the
earliest iteration. Iteration history lives in `IterationSnapshot`, not
in the finding list.

*Rejected alternative:* One `Finding` per mention, framework deduplicates
at scoring time. This would make the findings list a raw log rather than
a semantic artifact, and would complicate the hallucination verifier.

### D3 — Backwards-compatible field additions for schema evolution

`Trace` schema evolves via optional fields with default values. A v1.0.0
trace remains readable by v1.x readers. Breaking changes require a new
`schema_version` and an explicit rejection path.

*Rejected alternative:* Pydantic discriminated union per version. Correct
for v2.0.0+; premature for the hackathon timeline.

### D4 — Evidence excerpt length 10–200 characters, agent-emitted

The hallucination verifier checks `evidence_excerpt in raw_tool_output`.
Below 10 chars: too short for reliable matching, treated as unverifiable.
Above 200 chars: bloated trace files, diminishing verifier value.
Agents that cannot produce a qualifying excerpt have their finding flagged
as unverifiable — which is the correct outcome. It forces agents to produce
auditable evidence, not just claims.

---

## 3. Model Hierarchy
Trace
├── meta: TraceMeta            # identity, provenance, schema_version
├── config: ExperimentConfig   # full ablation parameterisation
├── tool_calls: ToolCall[]     # every invocation, references audit DB
├── iterations: IterationSnapshot[]  # state at each boundary
├── hypothesis_events: HypothesisEvent[]
├── findings: Finding[]        # canonical, deduplicated
├── verdict: Verdict | None
└── usage: UsageTotals

All models are `frozen=True`. The `Trace` is a read-only artifact of a
completed run.

---

## 4. Provenance

`Trace.sha256()` produces a stable content hash over canonical JSON
(sorted keys). `TraceMeta.sift_image_sha256` records the hash of the
evidence file the agent ran against. Together these allow a reviewer to
verify that a reported trace was produced from the claimed evidence and
has not been modified post-execution.

---

## 5. Hallucination Verifier Contract

`Finding.evidence_excerpt` is the operationalisation of "no hallucinations."
The verifier (Task 3) checks:

```python
evidence_excerpt in raw_tool_output_for(audit_entry_id)
```

A finding that fails this check is flagged `UNVERIFIED`. The framework
reports the unverified rate as a first-class metric. An agent claiming
zero hallucinations must produce a zero unverified rate — not a graph.

---

## 6. Consequences

**Positive:** Any agent implementing `to_trace()` is immediately comparable.
The framework is extensible without modification. Provenance is cryptographic.
Hallucination is measurable, not asserted.

**Negative:** Agents must emit structured confidence to appear in calibration
panels. Adapters for legacy agents (Protocol SIFT) require log parsing.
The evidence-excerpt discipline imposes overhead on agent prompt design.

---

## 7. Implementation

- `src/siftguard/eval/trace.py` — all Pydantic models
- `src/siftguard/eval/builder.py` — `TraceBuilder.from_db(conn, run_id)`
- `tests/eval/test_trace.py` — 17 tests, 17 passing
