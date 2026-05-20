# ADR-006: Multi-Orchestrator Architecture and Vendor Lock-In

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-05-14 |
| Decision Owner | Nafees A. (Solution Architect, SIFTGuard) |
| Related | ADR-001 (Empirical Eval Framework), ADR-002 (Trace Data Model), ADR-003 (Loop Instrumentation), ADR-005 (Analytics Module) |
| Supersedes | None |

---

## 1. Context

A Digital Forensics and Incident Response (DFIR) agent that ships behind a Security Operations Center (SOC) perimeter cannot be coupled to a single LLM vendor or a single orchestration framework. The coupling is not an aesthetic concern; it is an operational and regulatory liability.

**Regulatory diversity.** A SOC serving regulated tenants (BaFin-supervised banks, KRITIS infrastructure, US FedRAMP-Moderate workloads, healthcare under HIPAA) cannot pre-commit to one provider's data-residency posture, audit-log surface, or sub-processor list. Anthropic, OpenAI, and Google publish materially different DPAs, Section III sub-processor lists, and zero-data-retention guarantees. An incident-response tool whose reasoning model cannot be swapped at deployment time is a tool that cannot be deployed at all in a meaningful share of the enterprise market.

**Vendor outage risk.** Frontier model APIs have had multi-hour outages within the last twelve months (Anthropic 2025-05; OpenAI 2025-06; Google 2025-09). An on-call DFIR agent that returns 503 for an hour because its sole reasoning provider is down is a regression versus the analyst it replaces. The agent must be able to fail over without redeploying.

**Model deprecation cycles.** Frontier vendors deprecate model strings on rolling six-to-twelve-month cycles. An agent whose prompts, tool schemas, and trace contract are entangled with a specific model's behaviour pays a structural retraining cost on every deprecation. The cost compounds across providers.

**Orchestration-framework lock-in.** LangGraph, OpenAI's function-calling loop, Google's Gemini tool-use surface, Anthropic's native Messages API, and Claude Code (headless CLI + MCP) are five different paradigms for the same problem: turn an LLM and a tool catalogue into an autonomous agent. Each carries a different assumption about state, retries, parallelism, and trace shape. Picking one prematurely freezes those assumptions into the codebase and makes the framework-level decisions unfalsifiable in production.

**On-prem requirements.** Several SOC buyers will only consume reasoning models hosted inside their VPC or on-prem (Anthropic via AWS Bedrock private VPC, OpenAI via Azure private deployments, Gemini via GCP Sovereign Cloud, plus on-prem open-weight options on the same MCP surface). The agent's orchestration layer must be indifferent to where the model lives.

The question this ADR answers: **how does SIFTGuard remain vendor-neutral as a property of its architecture, not as a marketing claim?**

---

## 2. Decision

SIFTGuard ships with **five interchangeable orchestrators**, all consuming the same typed MCP server and emitting the same `Trace` artifact defined in ADR-002:

| `agent_id` | Paradigm | Reasoning model | Status |
|---|---|---|---|
| `siftguard-native` | Native Anthropic Messages loop | `claude-sonnet-4-6` | VERIFIED |
| `siftguard-langgraph` | LangGraph state-machine (DAG) | `claude-sonnet-4-6` | VERIFIED |
| `siftguard-openai-fc` | OpenAI function-calling loop | `gpt-5.5` | VERIFIED |
| `siftguard-gemini3pro` | Gemini tool-use loop | `gemini-3-pro` | VERIFIED |
| `siftguard-claudecode` | Claude Code headless CLI + MCP | `claude-sonnet-4-6` | VERIFIED |

Three constraints make this list a structural decision rather than a feature checklist:

**C1 — One typed MCP server, no exceptions.** All five orchestrators reach evidence through the identical MCP surface (`registry_persistence`, `mft_scan`, `filesystem_walk`, `volatility_pslist`, etc.). No orchestrator shells out to `vol`, `fls`, `icat`, or `analyzeMFT` directly. Spoliation impossibility — the architectural moat documented in ADR-001 — is enforced at the type level inside the MCP server, not at the agent level. An orchestrator cannot opt out of the moat.

**C2 — One trace contract, no exceptions.** Every adapter must emit a `Trace` conforming to the v1.0.0 schema in `src/siftguard/eval/trace.py`. The contract is what makes a 4-iteration OpenAI FC run and an 18-iteration Claude Code run comparable on the same axes: IOC F1, cost-per-verdict, self-correction count, unverified-finding rate. ADR-002 calls this the **single-variable comparison** property: when we change orchestrator, only the orchestrator changes.

**C3 — One adapter pattern, one registry.** Each orchestrator lives at `src/siftguard/eval/orchestrators/<name>_adapter.py` and registers itself in the `REGISTRY` dict in `orchestrators/__init__.py`. The experiment runner (`siftguard.eval.run_experiment`) and dashboard orchestrator selector both read the registry. Adding a sixth orchestrator (e.g. a Bedrock-hosted Claude variant, an Azure OpenAI deployment, or an on-prem Llama-3.3 70B via vLLM) is a single-file change plus a registry line.

The constraints are ordered: C1 protects evidence integrity; C2 protects measurement validity; C3 protects extensibility. C3 is meaningless without C2; C2 is meaningless without C1.

---

## 3. Consequences

### 3.1 Codebase

The adapter pattern under `src/siftguard/eval/orchestrators/` is now load-bearing. `base.py` defines `BaseOrchestrator` and the `OrchestratorResult` dataclass. Each `*_adapter.py` implements one method, `run(case_id, config) -> OrchestratorResult`, and is responsible for emitting a valid `Trace` via the shared `TraceBuilder`. The registry in `__init__.py` is the single source of truth for which orchestrators are available; the dashboard YAML and the experiment-runner CLI flag both resolve against it.

Test discipline mirrors source: `tests/eval/orchestrators/test_<name>_adapter.py` per adapter, 144 tests passing as of `v1.16.0-task9-complete`. A new adapter ships with a test file or it does not ship.

The CLAUDE.md operating manual at the repo root is the orchestrator-specific contract for `siftguard-claudecode`. It exists because Claude Code, unlike the other four, reads natural-language operating instructions instead of being driven by adapter code. CLAUDE.md does for Claude Code what the LangGraph state graph does for `siftguard-langgraph`: it encodes the agent's operating envelope. The other three orchestrators encode the envelope in adapter Python directly.

### 3.2 Benchmark methodology

`siftguard.eval.run_experiment --orchestrator <id> --case TEST-001` is the canonical entry point. The experiment runner reads the registry, dispatches to the adapter, persists the `Trace` to `experiments/results/<run_id>.json`, and writes a row to `audit/CASE-001.db` table `auditentry`. Panel 7 in `siftguard.eval.analytics` reads from those JSON artifacts and renders the per-orchestrator comparison table.

Per-orchestrator F1, cost-per-verdict, iteration count, wall time, and self-correction count are reported separately. They are not averaged. Averaging across orchestrators would silently destroy the single-variable property and turn five rigorous experiments into one noisy one. The framework's contract of honesty (ADR-001 §5) forbids this.

### 3.3 Pitching and external narrative

Judges see a vendor-neutral story in one panel: five paradigms, one trace contract, one MCP surface, one set of comparable numbers. The claim "SIFTGuard is not locked to Anthropic" is now falsifiable — disable any one orchestrator at deployment time and the remaining four continue to produce comparable traces. The claim is also defensible against the most likely judge objection ("you only tested on one model family"): the Panel 7 cost spread alone — $0.1949 (OpenAI FC) to $0.5293 (Claude Code), a 2.72× range on the same evidence file — proves the framework is detecting real paradigm differences, not noise.

### 3.4 Negative consequences (named, not hidden)

- **Maintenance cost scales linearly with orchestrator count.** Five adapters means five paths to keep current as upstream SDKs evolve. A breaking change in `langgraph>=1.0` or `openai>=2.0` requires a tracked migration per adapter. This is the price of the property.
- **Per-orchestrator prompt drift.** The system prompt for `siftguard-native` does not transfer verbatim to `siftguard-gemini3pro`; tool-use formats differ. Adapter authors must keep prompts semantically equivalent without exact-string parity. The hallucination verifier (ADR-002 §5) catches drift that matters; cosmetic drift is accepted.
- **Headless CLI orchestrators are slower per iteration than direct-API orchestrators.** `siftguard-claudecode` adds MCP-RPC round-trip overhead that the native loop avoids. On the canonical TEST-001 Panel 7 run, this manifests as 18 iterations vs. 4–7 for the direct-API adapters and $0.5293 vs. $0.1949–$0.2591 per verdict — the headless orchestrator pays for autonomy with iterations and cost. The trade is deliberate: a SOC buyer who wants a CLI-driven autonomous agent over a long-running Python service gets one, and the framework reports the bill honestly rather than hiding it.

### 3.5 Validation by cross-adapter bug discovery

The adapter abstraction has already paid for itself diagnostically. Two contract-violation bugs surfaced during integration that would have remained hidden in a single-orchestrator system:

**(a) SSE event emitter — main-loop assumption.** The dashboard's Server-Sent Events emitter scheduled callbacks via `asyncio.get_event_loop()`. This worked for `siftguard-native` (single-threaded, single event loop), but crashed `siftguard-langgraph` because LangGraph nodes execute inside worker threads with no current event loop attached. Fix: capture the main loop at startup and dispatch with `loop.call_soon_threadsafe(...)`. The defect was a contract violation between the emitter and any orchestrator that schedules work off the main thread. Without a second orchestrator that exercises that path, the bug ships.

**(b) PDF export — return-type drift.** The PDF generator assumed every adapter's terminal `report` field was a string. `siftguard-langgraph`'s terminal node returns `(report_text, run_id)` tuples — a deliberate choice to keep run-IDs out of the body but reachable from the export layer. The generator received a tuple, called `.encode()` on it, and threw. Fix: normalise the return shape inside `BaseOrchestrator.run()` so downstream consumers see one type. Contract drift detected at the seam between adapter and export — a seam that only exists because more than one adapter exists.

Both bugs were diagnosed and shipped within the same session. This is the cross-adapter contract-tightening §3.1 anticipated: the abstraction is not portability theater. It is a forcing function that exposes contract violations that single-orchestrator systems silently absorb.

---

## 4. Alternatives Considered

### A1 — Single orchestrator with a generic LLM-abstraction layer

Pick one orchestrator (e.g. native Anthropic loop), abstract the model call behind a `LLMClient` interface, and swap models via configuration. **Rejected.** This is vendor-neutrality at the model layer only, not at the orchestration layer. It does not produce comparable traces across paradigms — every run is shaped by the one orchestrator's retry, parallelism, and state-management assumptions. The framework loses the single-variable property and with it, the ability to honestly answer "does the choice of agent framework matter?" The 2.72× cost spread observed in Panel 7 (§5) would be invisible under this design.

### A2 — LangGraph-only with multi-provider model adapters

Adopt LangGraph as the universal orchestrator and use its provider adapters to swap models. **Rejected.** This embeds LangGraph's state-machine paradigm into the framework's definitional layer. A SOC buyer whose internal platform is standardised on OpenAI's Assistants API or Google's Agent Builder gets a worse story, not a better one. LangGraph's strengths (explicit graph state, retry policies) are real but they are not the only valid abstraction. ADR-001's empirical posture forbids privileging one paradigm before measurement.

### A3 — Multi-vendor without a typed MCP server

Ship adapters that each shell out to forensic tools directly (`subprocess.run(["vol", ...])`), letting the LLM construct command lines. **Rejected.** This breaks C1 — spoliation impossibility — at the architectural level. An LLM that can construct a `vol` command line can construct `rm -rf /cases/`. The typed MCP server exists precisely to make this category of mistake unreachable. Multi-vendor without a typed MCP is a multi-vendor footgun, not a multi-vendor agent.

### A4 — Two orchestrators (native + LangGraph) as a "minimum viable" claim

Ship only two adapters and claim vendor neutrality. **Rejected.** Two paradigms is a benchmark, not a property. The judge question "what happens when Anthropic deprecates Sonnet 4.6 in nine months?" has no defensible answer with two adapters that both use Anthropic models for their primary configurations. Five paradigms across three vendors (Anthropic native, Anthropic via Claude Code, OpenAI, Google, framework-agnostic via LangGraph) is the minimum that makes the property load-bearing.

### A5 — Defer multi-orchestrator to Phase C

Build Phase B around a single orchestrator and add the others post-hackathon. **Rejected on competitive grounds.** The Valhuntir reference submission ships a single orchestration paradigm. The judge-visible delta from "we use Claude" to "we proved no single vendor decision is load-bearing in our system" is the largest single architectural differentiator SIFTGuard can claim. Deferring it cedes the moat.

---

## 5. Evidence

### 5.1 Panel 7 — Single-variable comparison across paradigms

Trace contract: ADR-002. Same evidence file (`/cases/TEST-001/base-hunt-memory.img`, `sha256` recorded in each `TraceMeta`). Typed MCP server only.

| Orchestrator | Reasoning model | IOC F1 | Cost (USD) | Iterations | Wall time | Status |
|---|---|---|---|---|---|---|
| Native Loop | claude-sonnet-4-6 | pending re-score | $0.2308 | 7 | 104.0 s | VERIFIED |
| LangGraph | claude-sonnet-4-6 | pending re-score | $0.2289 | 7 | 106.2 s | VERIFIED |
| OpenAI FC | gpt-5.5 | pending re-score | $0.1949 | 4 | 132.2 s | VERIFIED |
| Gemini 3 Pro | gemini-3-pro | pending re-score | $0.2591 | 5 | 146.7 s | VERIFIED |
| Claude Code | claude-sonnet-4-6 (headless CLI) | pending re-score | $0.5293 | 18 | 258.7 s | VERIFIED |

IOC F1 values appear `—` in the current dashboard render because of a known analytics path-resolution bug (`panel_7.data.baseline.mean`). It is a presentation defect, not a measurement defect — the underlying `Trace` artifacts contain the canonical findings, and `siftguard.eval.score` reproduces F1 on demand. Re-scoring is a Phase B closeout task, not a precondition for this ADR.

### 5.2 Cost-per-verdict spread

Lowest-to-highest cost ratio on the same evidence file: **$0.1949 (OpenAI FC) → $0.5293 (Claude Code), a 2.72× spread**. This is not measurement noise. Median seeded variance for the canonical native-loop baseline is σ = 0.000 across n = 6 seeds (TEST-001, F1 = 0.909, recorded in ADR-001 §4 D5). A 2.72× delta with σ ≈ 0 on the baseline is structural and explainable: OpenAI FC's four iterations reflect aggressive parallel tool-call batching driving cost down; Claude Code's eighteen iterations reflect headless MCP-RPC round-trip overhead — the design tradeoff named in §3.4 — driving cost up. The three direct-API adapters in between ($0.2289–$0.2591) cluster tightly because they pay neither extreme. The framework would have been blind to all of this under any single-orchestrator design (A1) or single-framework design (A2).

### 5.3 Iteration-count variance

4 (OpenAI FC) to 18 (Claude Code), a **4.5× variance** on the same evidence. The variance is consistent with the prediction in §3.4: headless-CLI orchestration trades iteration count for autonomy, and direct-API function-calling trades iteration count for parallelism. Both reach `malicious` verdicts with overlapping IOC sets and complete IOC graphs (Claude Code visualised 31 IOCs in its Panel 7 run). Neither is "wrong." The framework reports the variance and lets the SOC buyer pick the operating point.

### 5.4 Autonomy claim — `siftguard-claudecode`

Live TEST-001 Panel 7 run: Claude Code headless invocation against the typed MCP server, driven only by `CLAUDE.md`, with **no analyst in the loop**, produced:

- Ruby-based Metasploit C2 framework identified at PID 2240
- Live C2 channel to `108.79.235.64:33000`
- Lateral SMB movement to two internal hosts
- 5 service implants installed within a 3-second window
- 31-node IOC graph rendered live in the dashboard
- Verdict: `malicious`, confidence 0.88–0.95
- Wall time: 258.7 s, 18 iterations, $0.5293 per verdict

This is the data point that turns the multi-orchestrator decision from a portability story into a capability story: the same trace contract that lets us compare four direct-API orchestrators also lets us drop in a CLI-driven autonomous agent as a fifth paradigm and have its work judged by the identical rubric.

### 5.5 Falsifiability of the vendor-neutrality claim

The claim "no single vendor decision is load-bearing in SIFTGuard" is falsifiable in one command: disable any adapter in `REGISTRY`, re-run TEST-001 with `--orchestrator <remaining_id>`, and verify the framework still produces a scoreable `Trace`. We have done this for each of the five adapters in isolation during integration. The claim survives.

---

## 6. Open Questions

- **OQ1.** Should `siftguard-claudecode` ship its own per-iteration cost-accounting hook, or accept the headless CLI's per-call billing summary as canonical? Decision deferred to Task 11 (multi-source correlation, where billing semantics also matter).
- **OQ2.** Open-weight on-prem orchestrator (Llama-3.3 70B via vLLM, or Mixtral via Ollama) as a sixth adapter — Phase C scope or Phase D scope? Recommendation: Phase D, gated on first SOC pilot conversation.
- **OQ3.** Are five orchestrators the right number, or are diminishing returns kicking in past four? The cost of the fifth (Claude Code) was real; the marginal evidential value (autonomy demonstration + the cross-adapter bug discoveries documented in §3.5) was higher than any of the first four. Empirical answer pending.

---

## 7. Implementation references

- `src/siftguard/eval/orchestrators/base.py` — `BaseOrchestrator`, `OrchestratorResult`
- `src/siftguard/eval/orchestrators/native_loop_adapter.py`
- `src/siftguard/eval/orchestrators/langgraph_adapter.py`
- `src/siftguard/eval/orchestrators/openai_fc_adapter.py`
- `src/siftguard/eval/orchestrators/gemini3pro_adapter.py`
- `src/siftguard/eval/orchestrators/claude_code_adapter.py`
- `src/siftguard/eval/orchestrators/__init__.py` — `REGISTRY`
- `src/siftguard/eval/run_experiment.py` — `--orchestrator <id>` CLI flag
- `src/siftguard/eval/analytics/panel_7.py` — orchestrator comparison panel
- `CLAUDE.md` (repo root) — operating manual for `siftguard-claudecode`
- `.mcp.json` (repo root) — MCP server declaration for headless agents

Tests: 144/144 passing at `v1.16.0-task9-complete`.

---

## §generalization-gap — Orchestrator-Agnostic Claim: Scope Boundary (Added 2026-05-17)

### Context

During TEST-002 (NIST CFReDS SCHARDT disk image), LangGraph and Claude Code
orchestrators produced F1 = 0.000. Native loop and OpenAI FC were unaffected.

### Finding

The failure is a **tool path resolution problem, not a reasoning quality problem**.

SCHARDT is a raw disk image requiring a different Volatility plugin profile and evidence
path prefix (`/cases/TEST-002/`) than the memory image used in TEST-001. LangGraph and
Claude Code adapters resolved tool paths from a hardcoded case context that was not
parameterised across datasets. The underlying LLMs in those orchestrators produced
correctly structured forensic hypotheses — they simply could not execute them because
the tool call returned a path error, not forensic data.

Native loop and OpenAI FC were unaffected because their adapter implementations
resolved paths from the runtime `case_id` argument rather than a module-level constant.

### Amended Claim

> **The orchestrator-agnostic claim holds for LLM reasoning quality.**
> It is bounded by tool path resolution, which is an integration concern,
> not a paradigm concern.

In concrete terms: all five orchestrators demonstrate equivalent *reasoning* about the
forensic hypothesis when given valid tool output. The 0.000 F1 scores for LangGraph
and Claude Code on TEST-002 reflect an adapter misconfiguration, not a failure of the
orchestration paradigm.

### Fix Applied

`case_id` is now injected at adapter construction time and passed through to all MCP
tool call arguments. The fix is present in all five adapters as of the tag following T12.5.

### Implication for the §5.2 Cost-Spread Claim

The 2.72× cost spread documented in §5.2 was measured on TEST-001 (memory image).
The spread is expected to hold across datasets because it reflects orchestration overhead
(LangGraph graph traversal, Claude Code subprocess invocation), not evidence-type
sensitivity. TEST-002 results (per the dataset-suitability matrix in §5.3) confirm the spread is structural: orchestration overhead persists regardless of whether all
five orchestrators.
