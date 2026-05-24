# ADR Pushback

Reviewed:
- `docs/adr/ADR-006-multi-orchestrator-vendor-lockin.md` as the requested ADR-006 multi-orchestrator ADR
- `docs/adr/ADR-007-spoliation-moat.md`
- `docs/adr/ADR-003-loop-instrumentation.md`

## ADR-006: Multi-Orchestrator Architecture and Vendor Lock-In

1. Weakest claim:

> "C1 — One typed MCP server, no exceptions. All five orchestrators reach evidence through the identical MCP surface..."

A senior reviewer will push back because the ADR turns an integration intention into an invariant. Five adapters across five SDK/CLI surfaces are exactly where bypasses, schema drift, prompt drift, and tool-call normalization bugs happen. "No exceptions" needs enforcement: a test that fails if any adapter imports tool implementations directly, shells out to forensic tools, or uses a schema not generated from the MCP catalog.

2. Missing alternative:

A more experienced architect would consider a **single orchestration kernel with provider-specific model/tool adapters**, not five full orchestrator adapters. Tradeoff: less paradigm purity and weaker "orchestration comparison" story, but much lower duplicated lifecycle/audit/error-handling surface. The ADR rejects LangGraph-only and generic LLM abstraction, but it does not address a middle design where planning/execution/audit state is centralized and only provider turn translation varies.

3. Hostile reviewer question:

"Show me the automated test that proves no orchestrator can bypass the MCP server or emit a non-conforming trace, and show me it failing when I add a direct `vol` subprocess call to one adapter."

4. Logical inconsistency:

Yes. ADR-006 says every adapter emits the same `Trace` and reaches tools through the identical MCP surface; ADR-003 says `SnapshotWriter` is the required choke point; ADR-007 says the MCP/type boundary enforces spoliation resistance. Those are mutually reinforcing on paper, but the ADRs do not share one enforceable contract. The result is three separate "single source of truth" claims.

## ADR-007: Architectural Evidence-Integrity Moat

1. Weakest claim:

> "Spoliation can be made mechanically impossible..."

This is the sentence a senior reviewer will attack. The ADR later admits TPM attestation, key rotation, cross-case correlation, and operational commitments are open questions, so "mechanically impossible" is too absolute. The defensible claim is narrower: specific mutation paths available through the agent's tool API are unrepresentable or rejected.

2. Missing alternative:

A more experienced architect would consider **OS-level confinement first**: run the MCP server in a chroot/container/seccomp/AppArmor profile with evidence mounted read-only and output mounted write-only, then treat typed MCP as defense-in-depth. Tradeoff: harder SIFT deployment and more operational friction, but it moves enforcement below Python and SQLite, which is where evidence-integrity guarantees belong.

3. Hostile reviewer question:

"If I have shell access to the workstation after a run, can I mutate the SQLite audit DB or extracted output files without SIFTGuard detecting it on the next read?"

4. Logical inconsistency:

Yes. ADR-007 claims data-layer append-only triggers, typed `EvidencePath` resolution, write-only MCP tools, and startup catalog mismatch failure. ADR-003 and ADR-006 depend on those controls, but ADR-003 also treats `SnapshotWriter` as the choke point. If the storage layer truly enforces append-only, `SnapshotWriter` is convenience, not enforcement. If `SnapshotWriter` is enforcement, ADR-007 overclaims.

## ADR-003: Agent Loop Instrumentation

1. Weakest claim:

> "For any verdict in any case, the reviewer can replay reasoning iteration-by-iteration..."

This overstates what instrumentation can prove. A reviewer can replay recorded state transitions, not the model's actual hidden reasoning or why it selected a token/tool. The ADR also assumes every adapter faithfully emits begin/end events and hypothesis events, which is exactly the failure mode instrumentation is supposed to detect.

2. Missing alternative:

A more experienced architect would consider **event-sourced tool-call logs as the primary record**, with iteration snapshots as derived materialized views. Tradeoff: more verbose storage and more reconstruction work, but stronger audit semantics: raw events are append-only facts, while "hypothesis state" and "self-correction" are interpretations that can be recomputed as schemas evolve.

3. Hostile reviewer question:

"What happens if an adapter reaches a verdict without emitting a `hypothesis_event`, or emits a clean-looking hypothesis event after the tool result that actually caused it was truncated or missing?"

4. Logical inconsistency:

Yes. ADR-003 says raw INSERTs are blocked at the application layer and data layer, and that append-only triggers catch raw writes. ADR-007 makes the same storage-layer claim. But ADR-003's own contract depends on adapter cooperation before and after model/tool calls. If an adapter bypasses the writer, the system may reject scoring, but that is not the same as exhaustive audit reconstruction.
