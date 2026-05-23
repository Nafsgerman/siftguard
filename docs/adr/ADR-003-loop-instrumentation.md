# ADR-003: Agent Loop Instrumentation (Per-Iteration Snapshots and Hypothesis-Revision Events)

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-05-17 (original) / 2026-05-19 (formalization) |
| Decision Owner | Nafees A. (Solution Architect, SIFTGuard) |
| Related | ADR-001 (Empirical Eval Framework), ADR-002 (Trace Data Model), ADR-005 (Analytics Module), ADR-006 (Multi-Orchestrator), ADR-007 (Spoliation Moat) |
| Supersedes | None |

---

## 1. Context

SIFTGuard's reasoning loop is autonomous and self-correcting: the agent picks a tool, runs it, observes the result, revises its working hypothesis, and either continues or terminates with a verdict. The loop is the part of the system that does the forensics. It is also the part of the system that is structurally hardest to defend without instrumentation.

**Why instrumentation is load-bearing, not optional.** A self-correcting loop that runs without structured tracing is observationally identical to a loop that hallucinates fluently. Both produce a verdict; both produce some plausible English describing how the verdict was reached; neither can distinguish a 3-iteration well-evidenced conclusion from a 12-iteration spinning loop that bottomed out on a heuristic. For a DFIR system whose output goes into a case file with legal weight, the indistinguishability is not an aesthetic problem — it is the system's fitness for purpose. A judge, a SOC lead, or an internal-review analyst must be able to reconstruct *why* a verdict was reached, not merely *that* it was reached.

**Why generic LLM telemetry is insufficient.** Vendor-supplied tracing — LangSmith for LangGraph, OpenAI's run-step API, Anthropic's request logging, Gemini's session traces — captures the model-call surface but is silent on the agent's reasoning structure. Tokens, latency, and tool names are present; hypothesis revisions are not. Worse, the trace shapes differ across vendors, which would make the orchestrator-comparison claim in ADR-006 unachievable: a metric that depends on which vendor's trace format happened to be in the loop is not a metric, it is a vendor preference.

**Why this ADR is a precondition for three other decisions.** The audit-trail expectation in ADR-007 (append-only DB) requires a *writer* that emits structured rows the audit DB can append. The single-variable comparison in ADR-006 requires a *contract* every orchestrator honours. The analytics module in ADR-005 requires a *queryable* representation of the loop's reasoning state. All three reduce to the same demand: every iteration of every orchestrator's loop must produce typed, immutable, queryable evidence of what the agent reasoned and why.

The question this ADR answers: **what is the minimum instrumentation contract that makes a self-correcting loop legible to a downstream auditor, comparable across orchestrators, and storable in an append-only audit log?**

---

## 2. Options Considered

| Option | Description | Failure mode |
|---|---|---|
| A | `stdout` / `stderr` line logging | Unstructured; unparseable cross-orchestrator; lossy under high iteration count |
| B | Vendor telemetry (LangSmith, OpenAI run-steps, Gemini sessions) | Vendor-specific; breaks ADR-006 comparability; silent on hypothesis revisions |
| C | Per-iteration JSON dumps to a file | Structured but unschema'd; no integrity guarantees; not queryable |
| D | Typed `SnapshotWriter` writing Pydantic-validated rows to the audit DB | The chosen design |

Options A–C fail the ADR-006 cross-orchestrator-comparability test for the same reason: their schemas are emergent rather than declared. Two orchestrators using the same option will produce traces that diverge in field names, units, and event taxonomy. Comparison becomes a manual translation exercise, which is what ADR-006's single-variable-comparison property exists to prevent.

Option D forces every adapter through the same writer, which forces every adapter to populate the same fields with the same semantics. The cost is a friction tax on adapter authors; the benefit is that the comparison is well-defined.

---

## 3. Decision

Two row types, written by a single `SnapshotWriter` choke-point, into the per-case audit DB defined in ADR-007.

### 3.1 Row type 1 — `iteration_snapshot`

One row per loop iteration. Schema (the migration lives at `migrations/003_iteration_snapshots.sql`):

```sql
CREATE TABLE iteration_snapshot (
    iteration_id        TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL,
    agent_id            TEXT NOT NULL,
    case_id             TEXT NOT NULL,
    iteration_index     INTEGER NOT NULL,
    tokens_in           INTEGER NOT NULL,
    tokens_out          INTEGER NOT NULL,
    cost_usd            REAL NOT NULL,
    latency_ms          INTEGER NOT NULL,
    confidence_vector   TEXT NOT NULL,   -- JSON: {hypothesis_id: confidence_float}
    hypothesis_state    TEXT NOT NULL,   -- JSON: working hypothesis object
    tool_calls_made     INTEGER NOT NULL,
    findings_emitted    INTEGER NOT NULL,
    timestamp_started   TEXT NOT NULL,
    timestamp_ended     TEXT NOT NULL
);
```

The single-writer discipline from ADR-007 §3.2 applies: all writes to these tables route through `SnapshotWriter`; no UPDATE or DELETE surface is exposed at the application layer. Storage-layer trigger hardening is deferred post-hackathon (see `LIMITATIONS.md`).

### 3.2 Row type 2 — `hypothesis_event`

Emitted whenever the agent's working hypothesis changes — promotion of a previously-marginal lead, demotion of a once-leading hypothesis, replacement of one hypothesis with another, or abandonment of a thread of inquiry. Schema:

```sql
CREATE TABLE hypothesis_event (
    event_id            TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL,
    iteration_id        TEXT NOT NULL REFERENCES iteration_snapshot(iteration_id),
    event_kind          TEXT NOT NULL CHECK (event_kind IN ('promote','demote','replace','abandon')),
    hypothesis_before   TEXT NOT NULL,
    hypothesis_after    TEXT,             -- NULL for 'abandon'
    evidence_cited     TEXT NOT NULL,    -- JSON list of finding_ids
    rationale_excerpt   TEXT NOT NULL     -- ≤512 chars; the model's stated reason
);
```

A single iteration may emit zero, one, or several `hypothesis_event` rows. An iteration that holds the working hypothesis steady emits zero. An iteration that abandons one lead and promotes another emits two.

### 3.3 The contract

Every orchestrator adapter (ADR-006) must, for every loop iteration:

1. Call `SnapshotWriter.begin_iteration(run_id, agent_id, case_id, iteration_index)` *before* any model invocation or tool call.
2. Emit any `hypothesis_event` rows the iteration produces, via `SnapshotWriter.emit_hypothesis_event(...)`, with `event_kind ∈ {promote, demote, replace, abandon}`.
3. Call `SnapshotWriter.end_iteration(...)` with token, cost, latency, and final hypothesis state.
4. On loop termination, call `SnapshotWriter.finalize(termination_reason)` with `termination_reason ∈ {verdict_reached, error}`.

The writer is the single choke point. Raw writes against `iteration_snapshot` or `hypothesis_event` that bypass `SnapshotWriter` are blocked at the application layer — the writer is the only module with an INSERT path into these tables. Storage-layer trigger enforcement (BEFORE UPDATE / BEFORE DELETE → ABORT) is documented hardening work. An adapter that bypasses the writer is not a SIFTGuard adapter; the experiment runner refuses to score a run whose iteration count in the orchestrator's emitted `Trace` does not equal the row count in `iteration_snapshot` for that `run_id`.

---

## 4. Consequences

### 4.1 Self-correction becomes a queryable property

Counting hypothesis revisions over a run is one SQL query:

```sql
SELECT event_kind, COUNT(*)
FROM hypothesis_event
WHERE run_id = ?
GROUP BY event_kind;
```

The Self-Correction Taxonomy on the dashboard is a direct visualization of this query, partitioned by `iteration_index` to produce the over-time view. The panel is the operational answer to "is this agent actually reasoning, or is it pattern-matching once and then narrating?" — for every run, a reviewer can count the moments at which the agent admitted, in structured form, that its working hypothesis was wrong and revised.

### 4.2 Cross-orchestrator comparability is mechanical

Two runs of the same case under different orchestrators (ADR-006) are now directly comparable on:

- Iteration efficiency: iterations to verdict, tokens per iteration, dollars per verdict.
- Self-correction profile: ratio of `promote` to `replace` events, count of `abandon` events per run.
- Tool selection: distribution of `tool_calls_made` across iterations.
- Confidence trajectory: the `confidence_vector` series across `iteration_index`.

None of these comparisons depend on which vendor's loop did the reasoning. The contract is the equalizer.

### 4.3 Audit reconstruction is exhaustive

For any verdict in any case, the reviewer can replay reasoning iteration-by-iteration: each iteration's tool calls, findings, token budget, and hypothesis state are present; each hypothesis revision is timestamped, evidence-linked, and accompanied by the model's stated rationale (capped at 512 characters to bound storage; the full rationale is in the iteration's tool-call trace if needed). Combined with ADR-007's append-only guarantees, the reconstruction is tamper-evident: the rows the reviewer reads are the rows that were written, and the order they were written in is the order the loop ran.

### 4.4 Friction on adapter authors

A new orchestrator adapter (a sixth paradigm — Bedrock Claude, on-prem Llama, a custom DAG framework) cannot ship without honouring the contract. The friction is intentional: the alternative is a sixth orchestrator whose traces are not comparable to the existing five, which would undo ADR-006. The base class `BaseOrchestrator` provides helper methods that handle the boilerplate; the adapter author writes the loop semantics, not the writer plumbing.

### 4.5 Write-path cost is negligible

A `SnapshotWriter` round-trip is a single SQLite INSERT against a local file. Measured cost: 3–5 ms per iteration on the SIFT VM, additive to LLM call latency (which dominates by three orders of magnitude). The cost does not change the operating economics of any orchestrator.

### 4.6 Schema evolution is append-only

Adding a field to `iteration_snapshot` is a forward migration (`migrations/00N_<description>.sql`), not an edit to migration 003. The append-only discipline of the audit DB (ADR-007) applies to its schema as much as to its rows.

---

## 5. Observability

The contract is consumed by three downstream surfaces:

1. **Dashboard — Self-Correction Taxonomy.** Reads `hypothesis_event` directly, partitioned by `run_id` and `iteration_index`. Renders the over-time view: for each iteration, the dots are events; the colour encodes `event_kind`.
2. **Dashboard — Multi-Orchestrator Comparison (Panel 7).** Aggregates `iteration_snapshot` across runs, grouped by `agent_id`. Cost-spread (ADR-006 §5.2, quoted in Devpost) and iteration-efficiency comparisons are computed from this table.
3. **Eval framework — Accuracy + Cost (Panel 1).** F1 numbers depend on `findings_emitted` consistency; cost-per-verdict depends on the summed `cost_usd` over a run's iterations.

A future audit-DB-mode scorer (ADR-009) will join `iteration_snapshot.findings_emitted` against the ground-truth IOC set directly, removing the report-text-parsing fallback. The schema in this ADR is the contract that scorer will consume.

---

## 6. References

- ADR-001 — Empirical evaluation framework (downstream consumer)
- ADR-002 — Trace data model (the aggregate view across `iteration_snapshot` rows)
- ADR-005 — Analytics module (the query layer over this contract)
- ADR-006 — Multi-orchestrator (the comparability property that depends on this contract)
- ADR-007 — Spoliation moat (the append-only guarantees this contract relies on)
- ADR-009 — Scorer source (the future audit-DB-mode scorer that will consume this contract)
- `src/siftguard/agent/instrumentation.py` — `SnapshotWriter` implementation
- `migrations/003_iteration_snapshots.sql` — Schema
- `tests/agent/test_instrumentation.py` — Contract tests
