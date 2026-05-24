# Gemini System-Level Architecture Risk Review

Context reviewed: `README.md`, `docs/architecture/architecture-v3.png`, `docs/THREAT_MODEL.md`, `docs/LIMITATIONS.md`, and ADRs covering empirical evaluation, trace model, loop instrumentation, analytics, multi-orchestrator design, spoliation moat, and audit-DB scorer.

## 1. Strongest Production-Readiness Objection

A hostile DFIR practitioner would say: this is a strong evaluation harness and demo agent, not a production DFIR system.

The concrete objection is chain-of-custody. The project markets "court-defensible autonomous DFIR," but the limitations file admits the opposite boundary: do not use it where the evidentiary chain must hold in court, because append-only audit discipline is enforced at the Python `SnapshotWriter` layer, direct SQL can mutate the SQLite DB, row-chain hashing is not implemented, and field-level IOC provenance is missing. A practitioner would also point to the operational limits: single workstation, single tenant, no RBAC, no live acquisition, no SOC integration, no network transport hardening, no multi-analyst workflow, soft Volatility timeouts, and only two public datasets.

The strongest version of the objection:

> "You have a promising offline benchmark and agent wrapper, but you do not yet have production chain-of-custody, provenance, concurrency, hard process isolation, or enough case diversity to claim operational DFIR readiness."

## 2. Most Important Differentiator

The single most important thing SIFTGuard does that a competing submission probably does not do is make the agent measurable across orchestration paradigms.

The five-orchestrator comparison is not just vendor theater. It gives judges a falsifiable matrix: same cases, same advertised tool surface, separate F1/cost/iteration outcomes, visible failure on TEST-002, and documented methodology. Most hackathon agent submissions show one impressive run. SIFTGuard shows the variance between agent architectures, including negative results. That is the strongest engineering contribution.

## 3. Biggest External Win Risk

The biggest risk outside the author's control is judge weighting.

If the judges reward polished end-user incident-response workflow and immediate analyst utility, Valhuntir or another narrower tool could beat SIFTGuard despite weaker architecture. SIFTGuard's strongest contribution is methodological: evaluation discipline, multi-orchestrator comparison, threat model, limitations, and guardrail analysis. That is exactly the kind of work a technical reviewer may value highly and a demo-oriented judge may undervalue if the live path depends on cached data, SIFT-specific setup, or explanation-heavy context.

Secondary external risk: the "court-defensible" phrase may trigger a harsher evidentiary standard than a hackathon project can meet. Once a DFIR judge hears that claim, they may judge it like a forensic product rather than like an agent benchmark.

## 4. Architectural Guardrails vs Prompt Guardrails

The claim is partly defensible, not fully defensible.

Defensible parts:
- The agent does not receive a generic shell tool.
- `safe_exec.py` has a binary allowlist, deny-pattern checks, and path validation.
- The MCP catalog contains read-oriented forensic tools rather than arbitrary OS primitives.
- The spoliation tests exercise real blocked destructive command paths.
- The architecture diagram correctly separates the prompt read-only instruction from the MCP/OS boundary.

Weakest enforcement point:

The architectural boundary is implemented mostly as Python application logic, not as an OS, storage, or generated type-system boundary.

Specific weak points:

1. MCP schemas are manually declared JSON objects, while tool handlers accept plain `dict` arguments. The `EvidencePath` Pydantic model exists, but the exposed tool schemas use strings. That makes "Pydantic-validated tools" weaker than advertised.
2. `extract_file` writes to caller-provided `output_path` after `icat` succeeds. That path is outside `safe_exec` argument validation and needs its own containment policy. A read-only tool with arbitrary output path is still a write primitive.
3. The audit moat is not storage-layer append-only. The threat model and limitations explicitly say direct SQL can mutate the DB and row-chain hashing is future work.
4. The active scorer remains report-text based per ADR-009. That means a prompt-format change can affect F1 and hallucination claims, so provenance is not fully architectural.
5. The five orchestrators do not all obviously traverse the same enforced MCP server boundary; several adapter paths import shared `_dispatch_tool` style code and provider-specific schema conversions. That is still architectural code, but it is not the same as forcing every call through one MCP server contract.

Ruthless bottom line:

The project has architectural guardrails against obvious destructive tool calls, but several headline claims still rely on prompt discipline, adapter cooperation, Python-layer conventions, and honest report formatting. The guardrail claim becomes fully defensible only after three changes: generated Pydantic tool specs enforced at MCP dispatch, OS-level evidence/output containment, and storage-level tamper evidence for the audit DB.
