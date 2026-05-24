# SIFTGuard Deep Consolidated Review

Generated: 2026-05-23

Scope: second-pass review of the five requested review tracks:

- Review 1: ADR pushback
- Review 2: code-level architecture review
- Review 3: test gap scan
- Review 4: system-level architecture risk
- Review 5: Devpost narrative pressure-test

This document reviews the five review outputs against the current repository. The goal is not to repeat the prior documents. The goal is to identify the deepest shared risks, correct overstatements, and turn the reviews into one next-sprint decision document.

## Executive Finding

SIFTGuard's strongest engineering asset is the measurable multi-orchestrator benchmark: five agent loops, common forensic tool surface, repeatable score/cost traces, and explicit negative results. That is unusual and valuable for a hackathon submission.

The central weakness across all five reviews is claim enforcement drift. The public story repeatedly says "typed", "append-only", "architectural", "court-defensible", and "same model weights", while the current implementation shows a softer reality: manual JSON schemas, plain `dict` MCP dispatch, Python-layer path checks, local SQLite mutability, field-level provenance gaps, and shared OS privileges between orchestrators and the MCP server.

The practical next sprint should not chase polish. It should close the gap between claimed guarantees and actual enforcement:

1. Harden filesystem containment in `safe_exec` and all write-producing tools.
2. Replace manual MCP tool schemas with Pydantic-backed `ToolSpec` registration and validation.
3. Make the audit/run lifecycle honest: either implement storage-level tamper evidence or downgrade all append-only/court-defensible claims.
4. Normalize orchestrator lifecycle through a shared context and runner so five adapters cannot drift in audit, timeout, parser, and tool-call behavior.
5. Rewrite the Devpost/Loom claims to say exactly what the repo proves today.

## Severity Map

| Severity | Theme | Why it matters |
|---|---|---|
| P0 | Filesystem containment and `extract_file.output_path` | A read-only forensic tool becomes a write primitive if output paths are caller-controlled or relative traversal is missed. |
| P0 | Data-layer append-only claims | ADRs and Devpost claim SQLite trigger enforcement, but the repo documents this as a future hardening gap and current code uses `UPDATE` / `INSERT OR REPLACE`. |
| P0 | "Same model weights" claim | The benchmark uses different provider models; "orchestration only" is not literally true as written. |
| P1 | MCP schema/type boundary | `EvidencePath` exists, but `server.py` exposes string schemas and `call_tool` accepts `dict`; that is not a fully typed boundary. |
| P1 | Orchestrator lifecycle drift | Five adapters individually handle run start, run completion, tool shapes, costs, parser failure, and timeouts. |
| P1 | Field-level provenance | "Zero hallucinated findings" is not provable until report fields are linked to exact tool output spans or structured extracted artifacts. |
| P2 | Self-correction taxonomy | Keyword classification is useful for dashboard analytics, but it is not the highest-risk next-sprint abstraction. |
| P2 | OS-level isolation | Full production hardening needs separate users, read-only mounts, containers, or seccomp-style constraints. This is larger than one sprint but should be named honestly. |

---

## Review 1 - ADR Pushback

### Finding 1: ADR-007 is the weakest ADR because its guarantees exceed current enforcement.

Weakest claim:

> "The schema is the contract. An orchestrator cannot smuggle in a shell call by formatting it as a tool argument - the Pydantic validator rejects it before the MCP server dispatches."

Reasoning: the repository has an `EvidencePath` Pydantic model in `src/siftguard/models/forensic.py`, but the live MCP server in `src/siftguard/mcp_server/server.py` declares tool inputs as manual JSON schemas with `"type": "string"` for paths. `call_tool(name, arguments)` receives a plain `dict` and dispatches it directly via `DISPATCH`. That means the actual boundary is not "Pydantic validator rejects it before dispatch"; it is "the called Python function and `safe_exec` hopefully reject it later." That distinction matters because the ADR is presenting the schema as the security boundary.

Risk: high.

Refactor or correction: split ADR-007 into "implemented controls" and "target controls." If the claim is meant to stand, implement generated tool schemas from Pydantic input models and validate every call at `call_tool` before handler dispatch. Use separate path types for evidence inputs and generated outputs: `EvidencePath`, `CacheOutputPath`, `ExportOutputPath`. Every executor should receive validated types, not raw strings.

### Finding 2: ADR-007 and ADR-003 conflict with the current audit-write model.

Weakest claim:

> "Append-only triggers from ADR-007 (`BEFORE UPDATE`, `BEFORE DELETE` -> `RAISE(ABORT, 'append-only')`) apply."

Reasoning: the current `SnapshotWriter` in `src/siftguard/agent/instrumentation.py` uses `UPDATE experiment_run SET ...` to complete a run and `INSERT OR REPLACE INTO iteration_snapshot` for iteration snapshots. Those are normal engineering choices for a mutable run-state table, but they conflict with an absolute append-only framing. Meanwhile `docs/THREAT_MODEL.md` and `docs/LIMITATIONS.md` explicitly say SQLite triggers and row-chain hashing are post-hackathon hardening, not implemented guarantees.

Risk: high.

Refactor or correction: choose one of two honest models. If you want append-only, convert mutable run completion into appended lifecycle events such as `experiment_run_started` and `experiment_run_completed`, and disallow `INSERT OR REPLACE`. If you want simple mutable run state for the hackathon, keep it, but remove "data-layer append-only" and "court-defensible" language from ADRs, Devpost, and Loom.

### Finding 3: ADR-006's experimental isolation claim is valuable but overstated.

Weakest claim:

> "The same model weights and the same Pydantic-validated tools are held fixed across all five adapters; orchestration is the only variable."

Reasoning: the Devpost table lists OpenAI FC with `gpt-5.5`, Native/LangGraph/Claude Code with Sonnet, and Gemini with Gemini 3 Pro. Those are not the same model weights. The project can still claim a strong benchmark, but the exact scientific claim should be "same evidence, same task, same intended tool surface, same scoring methodology, different model-provider plus orchestration stack." If you want "orchestration only," compare multiple orchestrators over the same provider/model, or define a subset of the benchmark where model weights are actually fixed.

Risk: high for judge credibility.

Refactor or correction: rename the claim from "orchestration is the only variable" to "orchestration/provider stack is the variable" unless you can run all five loops on the same underlying model. ADR-006 should explicitly separate model variance, framework variance, function-calling semantics, and Claude Code subprocess behavior.

### Finding 4: ADR-003 overclaims replayability.

Weakest claim:

> "For any verdict, a reviewer can replay the reasoning trajectory iteration-by-iteration."

Reasoning: instrumentation can replay visible state transitions, tool calls, costs, and final reports. It cannot replay hidden model reasoning or guarantee semantic equivalence of a later run. Also, `SnapshotWriter` failures are logged as warnings and not raised, so a run can continue with missing audit data. That is acceptable for a dashboard, but not for a strict replay or chain-of-custody claim.

Risk: medium.

Refactor or correction: say "audit visible decision state and tool-use trajectory" rather than "replay reasoning." Move toward event sourcing: append `model_call_started`, `model_call_completed`, `tool_call_started`, `tool_call_completed`, `parser_failed`, `retry_requested`, and `verdict_emitted` events. Then the replay claim can be about the external trace, not about internal cognition.

### Review 1 bottom line

The ADR set is directionally strong but too absolute. A senior reviewer will not object to the ambition; they will object to the mismatch between current enforcement and the words "mechanically impossible", "data layer", "Pydantic-validated", and "orchestration only." The sprint objective should be to make ADR language falsifiable and implementation-backed.

---

## Review 2 - Code-Level Architecture Review

### Finding 1: Keep the `BaseOrchestrator.run_case` refactor, but make it a run contract, not just a parameter cleanup.

File and function: `src/siftguard/orchestrators/base.py`, `BaseOrchestrator.run_case`

Smell: shotgun parameterization.

Reasoning: the protocol currently accepts case ID, evidence map, briefing, audit DB path, training mode, model ID, config override, ground truth path, and callback independently. This is already fragile. The deeper issue is that run identity, model identity, evidence identity, audit identity, scoring identity, cache identity, and event streaming identity are all part of one concept: an investigation run.

Refactor: introduce an `InvestigationContext` Pydantic model with nested models for case metadata, evidence manifest, model/runtime config, audit config, scoring config, and callback/event sink. The interface becomes `async def run_case(self, context: InvestigationContext) -> OrchestratorRunResult`. The result should be a typed object, not a tuple, with `run_id`, `final_report`, `terminated_reason`, `tool_calls`, `cost`, and `trace_status`. This turns the base protocol into a stable adapter contract instead of a long function signature.

Risk of leaving as-is: high. Every new capability, such as token budgets, cache policy, case manifests, replay mode, or live-vs-cached execution, will require signature changes across all five adapters.

### Finding 2: Promote MCP `ToolSpec` registration above all other code-level refactors.

File and function: `src/siftguard/mcp_server/server.py`, `TOOLS`, `DISPATCH`, `call_tool`

Smell: missing abstraction at the security boundary.

Reasoning: the MCP server manually declares JSON schemas and separately declares Python dispatch. This creates three sources of drift: docs/tool catalog, schema visible to models, and executor function signatures. It also weakens the "typed MCP" claim because the current `call_tool` path does not validate a Pydantic input model before invoking the handler.

Refactor: create a `ToolSpec` abstraction with:

- `name`
- `description`
- `input_model: type[BaseModel]`
- `output_model: type[BaseModel]`
- `executor`
- `access_policy`
- `tool_family`

The MCP `TOOLS` list should be generated from `input_model.model_json_schema()`. `call_tool` should perform `spec.input_model.model_validate(arguments)` and pass the typed model to the executor. Provider-specific schemas for OpenAI, Gemini, Claude, and LangGraph should also be generated from the same registry. This is the abstraction that makes "one tool surface" real.

Risk of leaving as-is: high, not medium. The risk is not just maintenance friction; it is boundary drift in the exact place the project uses as its core safety and benchmark claim.

### Finding 3: Replace ad hoc audit/run writes with a lifecycle service.

File and function: `src/siftguard/agent/instrumentation.py`, `SnapshotWriter`

Smell: missing abstraction plus leaky failure semantics.

Reasoning: `SnapshotWriter` currently owns low-level SQLite writes, run start, run completion, iteration snapshots, hypothesis events, and blocked mutation receipts. It silently logs write failures and continues. It also performs both append-like writes and mutable updates. Meanwhile each orchestrator imports or constructs `SnapshotWriter` separately and decides when completion is written. That makes audit completeness depend on adapter discipline.

Refactor: introduce a `RunLifecycleRecorder` or `AuditRecorder` facade with strict methods like `start_run`, `record_iteration`, `record_tool_call`, `record_parser_error`, `record_blocked_mutation`, and `finish_run`. The lifecycle recorder should expose policy: best-effort dashboard telemetry versus required audit writes. For benchmark runs, a required audit write failure should fail the run rather than merely log a warning. Underneath, choose either mutable run-state tables or append-only event tables, but make that a deliberate storage model.

Risk of leaving as-is: high. The system can produce a final report without a complete trace, which undermines the evaluation and "every claim traces" narrative.

### Finding 4: Demote `SelfCorrectionType` unification to P2.

File and function: `src/siftguard/models/correction_taxonomy.py`, `SelfCorrectionType`, `classify_correction`

Smell: leaky abstraction and heuristic classification.

Reasoning: the prior Review 2 called this a next-sprint refactor. It is real, but it is not more important than MCP validation or audit lifecycle. Keyword-based correction classification can mislabel dashboard analytics, but it does not create the same safety or chain-of-custody risk as path validation, output containment, or audit mutability.

Refactor: after the boundary work, define an `InvestigationEvent` model with structured event types shared by prompts, audit rows, and dashboard analytics. Replace substring classification with explicit event emission where possible.

Risk of leaving as-is: medium.

### Single biggest orchestrator-to-MCP boundary risk

The biggest risk is that MCP is currently a logical API boundary, not a hard security boundary. The orchestrators, MCP server, audit DB, cache directories, and evidence paths run in the same local workstation privilege domain unless the operator deploys extra OS controls. A malicious or compromised adapter does not need to "break MCP"; it can bypass MCP if it has shell, Python, filesystem, or subprocess access.

This does not make the project weak as a hackathon benchmark. It does mean "architectural guardrail" should be scoped to "inside the SIFTGuard MCP execution path", not to the whole host. Production spoliation resistance requires OS-level controls: read-only evidence mounts, output-only writable directories, separate Unix users, containerization, seccomp/AppArmor, and a tamper-evident remote or append-only audit sink.

---

## Review 3 - Test Gap Scan

### Finding 1: The highest-risk missing test is path containment across both input and output paths.

File and function: `src/siftguard/mcp_server/safe_exec.py`, `safe_exec`; `src/siftguard/mcp_server/tools/filesystem.py`, `extract_file`

Why high-risk: evidence integrity and host filesystem safety.

Reasoning: `safe_exec` only applies path validation to args starting with `/` or `./`. Relative forms like `../...` are not explicitly resolved through the evidence-root policy. Separately, `extract_file` writes bytes to caller-provided `output_path`, creates parent directories, and writes the file after `icat` succeeds. That is a write primitive independent of the read-only description in the tool catalog.

Test to add:

- Scenario: pass allowed binaries and path-like args such as `../../etc/passwd`, `../cases/TEST-001/base-hunt-memory.img`, `cases/../secret`, and absolute disallowed paths.
- Assertion: `SafeExecError` before subprocess creation.
- Scenario: call `extract_file` with `output_path` outside approved cache/export roots, including absolute and relative traversal forms.
- Assertion: `ForensicResult.outcome == FAIL`, no parent directories created, no file written.
- What it catches: traversal bypasses and accidental write access outside the intended artifact directory.

Priority: P0.

### Finding 2: The next missing test is real Pydantic validation at MCP dispatch.

File and function: `src/siftguard/mcp_server/server.py`, `call_tool`

Why high-risk: security boundary and benchmark contract.

Reasoning: tests can pass while the visible MCP schema, executor signature, and model classes drift. The project claims a typed MCP boundary, so tests should prove that invalid inputs fail at dispatch before any tool function or subprocess is reached.

Test to add:

- Scenario: call `call_tool("list_files", {"image_path": "../escape.E01"})` and `call_tool("extract_file", {"image_path": "/cases/x.E01", "inode": "1", "output_path": "../../out"})`.
- Assertion: validation rejects before the executor is invoked.
- Scenario: introspect every registered tool and assert schema is generated from the same input model used for runtime validation.
- Assertion: each tool has one authoritative schema source.
- What it catches: manual JSON schema drift and raw `dict` dispatch bypassing model validation.

Priority: P1, but it becomes P0 if the Devpost keeps saying "Pydantic-validated tools."

### Finding 3: Audit DB mutability and run lifecycle need tests that intentionally bypass the Python writer.

File and function: `src/siftguard/agent/instrumentation.py`, `SnapshotWriter`; migration/schema files for `experiment_run`, `iteration_snapshot`, `hypothesis_event`, `blocked_mutation`

Why high-risk: evidence integrity, repudiation, and claim credibility.

Reasoning: a direct SQLite connection can test the real storage boundary. If the intended guarantee is append-only at the data layer, `UPDATE` and `DELETE` must fail. If the intended guarantee is application-layer only, tests should assert the weaker behavior and docs should stop claiming more.

Test to add:

- Scenario: create a migrated audit DB, insert rows through the official writer, then open `sqlite3.connect` directly and attempt `UPDATE` and `DELETE` against audit tables.
- Assertion if keeping append-only claim: SQLite raises `OperationalError` with an append-only failure.
- Assertion if downgrading claim: docs and tests state this is not a protected boundary.
- Scenario: simulate `SnapshotWriter.write_experiment_run_complete` failure.
- Assertion: benchmark mode fails closed or marks the run invalid, rather than silently producing a report with incomplete audit metadata.
- What it catches: false chain-of-custody claims and partial traces.

Priority: P0 for docs/claims, P1 for implementation if claims are downgraded immediately.

### Finding 4: Orchestrator failure-mode tests need to cover malformed tool output, parser failure, and timeout finalization.

File and function: `src/siftguard/orchestrators/*_adapter.py`, `src/siftguard/agent/loop_v2.py`, adapter-specific parser/serializer paths

Why high-risk: external tool interaction and autonomous failure behavior.

Reasoning: the project has multiple loops over different model/tool APIs. A real DFIR run will hit timeouts, empty outputs, invalid JSON, provider SDK shape changes, and partial tool results. The important invariant is not "never fail"; it is "fail with a final trace row and an honest terminated reason."

Test to add:

- Scenario: mock a tool to return malformed JSON or a `ForensicResult` missing expected fields.
- Assertion: the orchestrator logs parser failure, does not hallucinate a finding from the broken output, and either retries or terminates with `terminated_reason="error"`.
- Scenario: mock an LLM call or tool call timeout in the second iteration.
- Assertion: run completion is written, cost/tokens so far are preserved, no further tool calls occur, and the event stream receives a terminal error state.
- What it catches: orphaned runs, dashboard hangs, and false successful reports after parser failure.

Priority: P1.

---

## Review 4 - System-Level Architecture Risk

### Finding 1: The strongest hostile objection is chain-of-custody, not just scale.

Question: If a hostile DFIR practitioner reviewed this system, what is the strongest objection to production-readiness?

Answer: SIFTGuard is a strong offline evaluation harness and demo agent, not yet a production chain-of-custody system. The strongest objection is that the same local workstation trust boundary covers the agent, MCP server, evidence filesystem, audit DB, cache, and reports. Current docs also admit no storage-layer append-only enforcement and no row-chain hash. That makes "court-defensible autonomous DFIR" too strong.

Scale concerns are real: single workstation, SIFT-specific assumptions, Volatility latency, soft timeouts, and no multi-analyst/RBAC/SOC integration. But the harder objection is evidentiary: a production DFIR tool must prove who had write access to what, when, and how tampering is prevented or detected outside application code.

### Finding 2: The biggest differentiator is the benchmark discipline.

Question: What does SIFTGuard do that a competing submission probably does not?

Answer: it makes agent architecture measurable. Five orchestrators, one intended tool catalog, shared cases, shared scoring, cost/iteration/wall-time reporting, and documented failures are a serious differentiator. Most hackathon entries demonstrate one happy path. SIFTGuard can show a matrix and explain why some paradigms fail.

Keep this as the center of the submission. It is more defensible than "court-defensible."

### Finding 3: The biggest outside-control win risk is judge weighting.

Question: If betting on the submission winning, what is the biggest external risk?

Answer: judge preference. If judges reward immediate analyst workflow polish, visual UX, or live incident-response readiness, a narrower competitor can win. SIFTGuard's strongest contribution is methodological and architectural, which depends on judges valuing evaluation rigor over demo smoothness.

Secondary risk: live API/provider instability. A multi-provider demo is more exposed to SDK changes, rate limits, latency spikes, model availability, and Claude Code CLI behavior than a single local deterministic tool.

### Finding 4: Architectural guardrails are partly defensible but not fully defensible.

Question: Is "architectural guardrails over prompt guardrails" fully defensible?

Answer: no. The claim is defensible inside the happy-path MCP wrapper, but not at the whole-system level.

The weakest enforcement points are:

- `src/siftguard/mcp_server/server.py` manually declares string schemas and dispatches raw `dict` arguments.
- `src/siftguard/models/forensic.py` defines `EvidencePath`, but the MCP server does not enforce it for the exposed tools.
- `src/siftguard/mcp_server/tools/filesystem.py` exposes `extract_file.output_path` as a caller-provided write path.
- `src/siftguard/mcp_server/safe_exec.py` performs Python-layer command/path checks rather than OS confinement.
- `src/siftguard/agent/instrumentation.py` uses mutable SQLite writes and logs write failures as warnings.
- The active audit/provenance model does not prove field-level report literals came from exact tool output bytes.

The credible phrasing is: "SIFTGuard moves major safety controls from the prompt into a typed MCP execution layer, but full spoliation resistance still requires OS-level and storage-level hardening."

---

## Review 5 - Devpost Narrative Pressure-Test

### Finding 1: The Devpost overclaims experimental isolation.

Quote:

> "The same model weights and the same Pydantic-validated tools are held fixed across all five adapters; orchestration is the only variable."

Reasoning: the table names different provider models. This is the fastest credibility failure because a judge can see it on the same page. Also, the tools are intended to be common, but the currently exposed MCP schemas are not fully Pydantic-enforced at dispatch.

Rewrite:

> "The same cases, scoring methodology, prompts, and intended MCP tool catalog are held fixed while the model-provider/orchestration stack changes. The benchmark measures the practical behavior of those stacks under the same forensic workload."

### Finding 2: The Devpost overclaims the audit DB.

Quote:

> "Append-only audit DB. SQLite with insert-only access enforced at the data layer."

Reasoning: this is currently false as an implementation claim. The threat model and limitations already say storage-level triggers and row-chain hashing are future work. The writer also uses update/replace semantics.

Rewrite:

> "Audit DB records run metadata, tool calls, iteration snapshots, and blocked-mutation receipts through a shared application writer. Storage-layer append-only triggers and row-chain hashing are documented hardening work."

### Finding 3: The Devpost overclaims spoliation proof.

Quote:

> "Spoliation test suite: 12/12 attacks blocked architecturally at the MCP layer - not by prompt"

Reasoning: the test suite blocks a useful set of destructive command patterns, but it does not cover relative traversal or every output write path. The statement "12/12 attacks blocked" is fine if scoped to the named suite. It is not proof of a complete moat.

Rewrite:

> "The spoliation suite blocks 12 named destructive command scenarios at the MCP execution layer; next hardening adds traversal/output-path containment tests and OS-level read-only evidence mounts."

### Finding 4: "Zero hallucinated findings" needs field-level provenance before it is safe.

Quote:

> "Zero hallucinated findings - every claim traces to an audit DB row."

Reasoning: tracing a report to an audit row is not the same as proving every literal in the report came from tool output. A model can produce a plausible IP, process name, or hash unless the parser/scorer maps structured findings to tool-output spans.

Rewrite:

> "Every reported finding is expected to cite a tool-execution row; field-level provenance is tracked as hardening work to prove exact literal extraction."

### Finding 5: "Court-defensible" should be replaced with "tamper-aware prototype" unless the storage/OS boundary is implemented.

Quote:

> "Court-defensible autonomous DFIR."

Reasoning: court-defensible is a legal/evidentiary standard. The repo has valuable audit discipline, but also documented limitations: no storage-layer append-only, no row hash chain, no field-level provenance, no hard OS containment, no multi-analyst chain-of-custody workflow. That phrase invites judges to apply a production forensic-product standard.

Rewrite:

> "Audit-first autonomous DFIR benchmark for SIFT Workstation, with explicit evidence-integrity guardrails and documented chain-of-custody hardening."

### Finding 6: The "Challenges" section should admit a harder real challenge.

Do not invent severe SQLite lock contention unless logs prove it. A more credible hard challenge is:

> "Turning a promising MCP wrapper into a real evidence-integrity boundary was harder than making the agent work. The first implementation blocked obvious destructive commands, but the review surfaced that Python-layer path checks, local SQLite writes, and shared workstation privileges are not the same thing as OS/storage enforcement. We documented that gap and scoped the next hardening step: generated Pydantic tool specs, output-path containment, storage-level tamper evidence, and read-only evidence mounts."

This is more honest than a generic "schema mismatch" challenge, and it directly addresses the most likely senior-reviewer objection.

### Finding 7: Loom script claims the demo cannot visibly prove.

Self-correction sequence: the Loom can show dashboard state, but it cannot prove the taxonomy is semantically correct unless the underlying events are structured. If it is based on keyword classification, say "dashboard classifies correction events" rather than implying rigorous semantic self-correction.

Multi-orchestrator comparison: the Loom uses cached runs. That is fine for a two-minute demo, but the narration should not imply all five runs are executing live. Say "we replay the recorded benchmark matrix" or "the dashboard binds to completed benchmark runs."

Spoliation moat: running `tests/spoliation/test_spoliation.py` proves the named scenarios, not the whole moat. Add a sentence in narration or on-screen text: "named destructive-command scenarios" rather than "the architecture is the wall."

---

## Cross-Review Synthesis

### Systemic Risk 1: Boundary claims are ahead of boundary enforcement.

This appears in all five reviews. The architecture says MCP/Pydantic/append-only/typed/path-safe. The implementation is closer to manual schemas, raw dictionaries, Python checks, caller-provided paths, and mutable local SQLite.

Sprint action: implement `ToolSpec` plus typed path models and path policies. Update claims immediately if implementation cannot land before submission.

### Systemic Risk 2: Audit exists, but provenance is not yet strong enough for the narrative.

SIFTGuard records useful rows. That is not the same as immutable audit, exact replay, or zero hallucinations. These are three different guarantees:

- auditability: a run has recorded events and outputs;
- tamper evidence: rows cannot be changed undetected;
- field provenance: each reported literal maps to source tool output.

Sprint action: separate these terms in docs. Implement the first thoroughly, roadmap the second and third unless there is time.

### Systemic Risk 3: The multi-orchestrator story is strong, but "orchestration only" is not literally correct.

The project can win on the empirical matrix without pretending model weights are held fixed. The stronger, more honest claim is that SIFTGuard measures real deployment stacks under the same workload and scoring method.

Sprint action: rewrite ADR-006, README, Devpost, and Loom language to separate model, provider API, tool-calling semantics, and orchestration framework.

### Systemic Risk 4: Five adapters multiply lifecycle drift.

Each adapter can drift in how it validates tool output, records audit rows, handles malformed responses, calculates cost, emits terminal state, and calls MCP. The architecture wants one contract, but some enforcement is still convention.

Sprint action: shared `InvestigationContext`, shared `RunLifecycleRecorder`, shared `ToolInvoker`, shared parser failure policy.

### Systemic Risk 5: The submission should lean into "evaluation rigor", not "forensic product readiness."

SIFTGuard is unusually credible as an AI-systems benchmark for autonomous DFIR. It is less credible if judged as a production forensic chain-of-custody product. The current narrative sometimes invites the harsher standard.

Sprint action: change the headline from "court-defensible autonomous DFIR" to an audit/evaluation-focused phrase unless the hardening lands.

---

## Next-Sprint Refactoring Plan

### P0: Fix claim-breaking security gaps.

1. Harden `safe_exec` path handling. Resolve every argument that is path-like, reject `..`, reject unknown absolute prefixes, and test relative traversal.
2. Add output containment for `extract_file`, `create_supertimeline`, `sort_timeline`, and any tool that writes generated artifacts. Outputs should be under configured cache/export/report roots only.
3. Remove or rewrite public claims about data-layer append-only DB enforcement until triggers or row-chain hashing exist.
4. Rewrite "same model weights" everywhere it appears.

### P1: Make the MCP boundary genuinely typed.

1. Add `ToolSpec` registry.
2. Define Pydantic input models for every MCP tool.
3. Generate MCP JSON schemas from those input models.
4. Validate `arguments` at `call_tool` before executor invocation.
5. Generate provider-specific tool schemas from the same registry so OpenAI/Gemini/Claude/LangGraph do not drift.

### P1: Normalize run lifecycle.

1. Create `InvestigationContext`.
2. Replace tuple returns with `OrchestratorRunResult`.
3. Create a shared lifecycle recorder for run start, iteration, tool call, parser error, blocked mutation, and run completion.
4. Decide explicitly whether audit storage is mutable run state or append-only events.
5. Make required audit failures fail the benchmark run, not just log a warning.

### P1: Add the missing tests.

1. Traversal and output-path containment tests.
2. MCP dispatch validation tests.
3. Direct SQLite mutation tests aligned to the actual claim.
4. Timeout/malformed-output/parser-failure tests for each orchestrator family or through a shared harness.

### P2: Upgrade provenance and dashboard semantics.

1. Field-level IOC provenance from structured tool outputs.
2. Audit-DB-backed scorer that does not depend only on final report text.
3. Structured self-correction events instead of keyword classification.
4. OS-level containment design: read-only evidence mount, separate users, container profile, or equivalent SIFT-compatible sandbox.

---

## Final Recommendation

For hackathon submission, the winning version of SIFTGuard is:

> "An audit-first autonomous DFIR benchmark that compares five agent orchestration stacks on one forensic MCP tool surface, with explicit guardrails and transparent limitations."

The risky version is:

> "Court-defensible autonomous DFIR with mechanically impossible spoliation and zero hallucinations."

The first claim is strongly supported by the repo and the review set. The second claim requires more hardening than the current code shows. The next sprint should make that distinction explicit, fix the P0 boundary gaps, and let the architecture story become sharper because it is more honest.
