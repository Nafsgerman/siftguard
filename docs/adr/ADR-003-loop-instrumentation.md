# ADR-003: Agent Loop Instrumentation

Date: 2026-05-17
Status: Accepted
Deciders: Nafees Ahmad

## Problem

SIFTGuard's self-correcting agent loop runs autonomously across N iterations. Without
structured instrumentation there is no way to:
- Distinguish reasoning progress from spinning
- Reconstruct *why* the agent reached a verdict
- Prove to auditors that loop termination was principled, not arbitrary
- Give judges observable evidence that the loop is reasoning, not hallucinating

## Options Considered

### Option A: stdout / stderr logging
Simple. Loses structure. No queryable audit trail. No replay capability.

### Option B: In-memory event bus
Fast. Ephemeral — dies on process restart. Cannot satisfy spoliation requirements.

### Option C: Append-only SQLite tables (`iteration_snapshot` + `hypothesis_event`)
Persistent. Queryable. Append-only by convention. Integrates with the spoliation moat
(ADR-007). Each iteration writes a snapshot; each hypothesis revision is a typed event row.

## Decision

**Option C.** Two tables are introduced, written exclusively via `SnapshotWriter`.

### `iteration_snapshot`

| Column | Type | Purpose |
|---|---|---|
| `id` | INTEGER PK | Row identity |
| `agent_id` | TEXT | Orchestrator instance discriminator |
| `experiment_run_id` | INTEGER FK | Parent run |
| `iteration` | INTEGER | Loop counter (0-based) |
| `hypothesis` | TEXT | Agent's current working theory |
| `tools_called` | TEXT | JSON array of tool names invoked this iteration |
| `findings_so_far` | TEXT | JSON snapshot of accumulated IOCs |
| `confidence` | REAL | Self-assessed confidence [0.0–1.0] |
| `timestamp` | TEXT | ISO-8601 UTC |

### `hypothesis_event`

| Column | Type | Purpose |
|---|---|---|
| `id` | INTEGER PK | Row identity |
| `agent_id` | TEXT | Orchestrator instance discriminator |
| `experiment_run_id` | INTEGER FK | Parent run |
| `iteration` | INTEGER | Loop counter at time of event |
| `event_type` | TEXT | `hypothesis_formed` \| `hypothesis_revised` \| `hypothesis_confirmed` \| `hypothesis_rejected` |
| `prior_hypothesis` | TEXT | What the agent believed before |
| `posterior_hypothesis` | TEXT | What it believes now |
| `evidence_delta` | TEXT | JSON: what new evidence caused the revision |
| `timestamp` | TEXT | ISO-8601 UTC |

## Why Instrumentation Before Observability

The observability dashboard (Panel 7) was built *after* these tables existed. This was
deliberate: the write path is the source of truth. The UI reads from it. Reversing this
order would have made the dashboard a driver of schema design, coupling presentation
to forensic semantics.

This is an inversion of the common "add logging later" anti-pattern. For an autonomous
agent making evidentiary claims, the instrumentation *is* the product.

## Consequences

### Positive
- Full iteration-by-iteration replay for any agent run without re-running the agent
- `hypothesis_event` provides an explanation trace satisfying chain-of-custody expectations
- Dashboard panels derive from the same tables — no divergence between what the UI
  shows and what actually happened
- Judges can query `iteration_snapshot` to verify reasoning without running the agent

### Negative
- Every iteration incurs a synchronous SQLite write — acceptable given Volatility plugin
  latency dominates total iteration time by 2–3 orders of magnitude
- Schema changes require a migration — mitigated by the existing Alembic path

### Bounded Risk
Tables are append-only by convention enforced at the application layer, not the DB layer.
A future task should add a SQLite trigger rejecting UPDATE/DELETE on these tables.
A row-level SHA-256 chain hash (similar to blockchain transaction linking) is the
recommended post-hackathon hardening step.
