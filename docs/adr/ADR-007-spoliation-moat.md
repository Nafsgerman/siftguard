# ADR-007: Architectural Evidence-Integrity Moat (Spoliation Resistance as a Property of the System)

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-05-19 |
| Decision Owner | Nafees A. (Solution Architect, SIFTGuard) |
| Related | ADR-001 (Empirical Eval Framework), ADR-002 (Trace Data Model), ADR-003 (Loop Instrumentation), ADR-006 (Multi-Orchestrator), ADR-009 (Scorer Source) |
| Supersedes | None |
| Tag at decision | v1.29.0-task24-devpost |

---

## 1. Context

A digital-forensics agent that touches evidence is, by default, a liability. Evidentiary chains in DFIR have legal weight that survives the incident: court-admissibility doctrines (FRCP 37(e) in the United States, StPO §244 and §261 in Germany, ENISA's electronic-evidence guideline in the EU) treat alteration or destruction of evidence — *spoliation* — as grounds for adverse inference, sanctions, or outright dismissal. The bar is not "the analyst did the right thing." The bar is "no party with access to the evidence could have altered it, and the system can prove that to a court-appointed expert."

A purely autonomous agent inherits the same bar and fails it twice over. First, the agent is a non-deterministic process: model output varies run-to-run, and a verdict that depends on which side of a sampling distribution the model landed on is not reproducible evidence. Second, and more dangerously, the agent has read-write access to its own working memory, its tool outputs, and — without architectural defense — to the same evidence it is investigating. A jailbroken or prompt-injected agent that *modifies* the artifacts it reports on does not merely produce a wrong answer; it contaminates the case file.

**Prompt-level defense is insufficient.** "Do not modify evidence" in a system prompt has the failure modes Anthropic, OpenAI, and Google all document: indirect prompt injection through evidence contents (an attacker embedding instructions inside a packet capture, an email body, or a registry key value), training-data drift across model versions, and the well-rehearsed jailbreak corpus. Treating spoliation as a behavioural property of the model — something the model is supposed to refrain from — moves the burden to the wrong layer. The court does not care what the model was told. The court cares what the system could do.

**The architectural alternative.** Spoliation can be made *mechanically impossible* — not in the sense of perfect security, which is unattainable, but in the precise sense that mutation pathways the agent could plausibly traverse are absent from the system. The agent has no write handle to evidence. The audit log it does have a handle to is append-only at the storage layer. The methodology under which a verdict was produced is content-addressed. A spoliation attempt is not "blocked by policy"; it is "not a representable operation."

The question this ADR answers: **what does evidence-integrity look like when it is a property of the architecture rather than a property of the prompt?**

---

## 2. Options Considered

| Option | Description | Failure mode |
|---|---|---|
| A | System-prompt prohibition | Defeated by indirect prompt injection; not auditable |
| B | Filesystem read-only mount of evidence | Partial — covers raw evidence but not the audit DB or the tool-call surface |
| C | Per-orchestrator RBAC / sandbox | Five orchestrators (ADR-006) → five sandbox specifications → none of them composable |
| D | Architectural moat: typed MCP + append-only DB + content-addressed methodology | The chosen design |

Options A–C all share a common defect: they move enforcement to a layer above the data plane. The agent (or the orchestrator hosting the agent) is invited to be well-behaved. Option D moves enforcement *into* the data plane: mutation operations either do not exist in the API the agent can call, or fail at the storage layer with a recorded receipt.

---

## 3. Decision

Evidence integrity in SIFTGuard rests on three layered controls, each enforced below the agent layer. The agent — and the orchestrator hosting it — cannot opt out of any of them.

### 3.1 Control 1 — Typed MCP Boundary

Every forensic tool is exposed to the agent as a Pydantic-validated MCP function with a frozen, version-pinned schema. There is no `shell()` tool, no `read_file()` tool that accepts arbitrary paths, no `sql()` tool. The catalog is small, opinionated, and read-only with respect to evidence:

- `volatility_pslist`, `volatility_netscan`, `volatility_malfind` — memory analysis, read-only
- `mft_scan`, `filesystem_walk`, `registry_persistence` — disk analysis, read-only
- `report_finding`, `emit_ioc`, `set_verdict` — write-only into the audit DB; never into evidence

The schema is the contract. An orchestrator cannot smuggle in a shell call by formatting it as a tool argument — the Pydantic validator rejects it before the MCP server dispatches. An evidence path is type `EvidencePath`, a closed enumeration resolved against the case manifest; an agent cannot construct a path to anything not declared in the manifest at case open.

The catalog is auto-generated and version-pinned. Schema reference: [`docs/TOOL_CATALOG.md`](../TOOL_CATALOG.md). Tool catalog generation is automated under T22 and produces a manifest that the typed MCP server validates against at startup; mismatch is a fatal error, not a warning.

### 3.2 Control 2 — Append-Only Audit DB

The audit database (`audit/<case_id>.db`, SQLite) is the system of record for every tool call, every finding, every IOC, every verdict, and every hypothesis revision. Three properties enforce its append-only character at the storage layer:

1. **Insert-only triggers.** Every audited table carries `BEFORE UPDATE` and `BEFORE DELETE` triggers that `RAISE(ABORT, 'append-only')`. The trigger fires regardless of caller — application code, ORM, a misconfigured migration, or a malicious `INSERT OR REPLACE` attempt all fail at COMMIT time. The SQL constraint sits in the same file as the schema; it cannot be reasoned about separately from the data model.
2. **Versioned migrations.** Schema migrations are themselves append-only. Migration N+1 references the SHA-256 of migration N's applied state. A schema rollback is not a representable operation; a forward migration with explicit data transformation is. Migration drift between deployments is detected at startup.
3. **Recorded blocks.** Every failed mutation attempt — whether from agent code, orchestrator harness, or operator error — emits a `spoliation_attempt` row containing the attempted action, the reason for rejection, the actor identity, and a timestamp. The receipts are themselves append-only. An attacker silencing the receipt log is the same operation as an attacker silencing the audit log, and is caught by the same trigger.

The agent's only write path into the audit DB is through `SnapshotWriter` (ADR-003) and the typed write-only MCP tools (`report_finding`, `emit_ioc`, `set_verdict`). All three funnel through INSERT-only code paths. The writer does not expose UPDATE or DELETE methods at any level of the API.

### 3.3 Control 3 — Content-Addressed Methodology

Every report emitted by SIFTGuard is stamped with a methodology header:
methodology_version: 1.2.0
methodology_sha256:  9c2e…b4f7
tool_catalog_sha256: 4a8d…12cc
ground_truth_version: 1.1.0

The `methodology_sha256` is the SHA-256 of `docs/EVAL_FRAMEWORK.md` at the moment of the run. Changing scoring rules — narrowing the definition of an IOC, broadening the verdict taxonomy, altering the false-positive threshold — bumps the methodology version and changes the SHA. Reports produced before the change remain attributable to the methodology that produced them; reports produced after the change are not retroactively comparable. The methodology cannot be silently rewritten.

This control closes the loop on Controls 1 and 2: it would be possible, in principle, to ship an audit DB that is append-only but produced under a scoring rule that was changed after the fact to favour the agent. Content-addressing the methodology makes that operation visible.

---

## 4. Verification

The claim "spoliation is architecturally impossible" is mechanically verifiable. The 12-test spoliation suite (`tests/spoliation/`) exhaustively attempts every category of mutation a hostile agent or operator might attempt, and asserts the attempt is blocked at the data plane:

| # | Attempt | Expected outcome |
|---|---|---|
| 1 | `UPDATE findings SET …` from agent code path | Trigger ABORT; receipt row written |
| 2 | `DELETE FROM iocs WHERE …` from orchestrator harness | Trigger ABORT; receipt row written |
| 3 | `INSERT OR REPLACE` on `iteration_snapshot` | Trigger ABORT; receipt row written |
| 4 | Direct `sqlite3` shell write to audit DB after agent run | Trigger ABORT at next read; case marked tainted |
| 5 | Tool call with shell metacharacters in `EvidencePath` | Pydantic validator rejects pre-dispatch |
| 6 | Attempted MCP call to undeclared tool name | Server returns `unknown_tool`; receipt written |
| 7 | Evidence-file write attempt through `report_finding` | Type-system rejection: `report_finding` has no path argument |
| 8 | Migration rollback attempt | Migration runner refuses; SHA mismatch detected |
| 9 | Methodology edit between runs without version bump | Startup check fails; service refuses to begin a new run |
| 10 | Tool catalog edit without regeneration | Startup mismatch; service refuses to begin a new run |
| 11 | `DELETE FROM spoliation_attempts` | Trigger ABORT; recursive receipt written |
| 12 | Agent prompt-injected to emit `DROP TABLE` as IOC value | IOC value type-validated; injection neutralized as data, not code |

The suite runs on every push to `main` (T18 CI) and on every release-tag build (T21). Coverage is 12/12 at the time of writing. The suite is the operational definition of the moat: as long as it passes, the architectural claim holds.

---

## 5. Consequences

### 5.1 Positive

**The integrity claim becomes a property a reviewer can run, not a sentence in a brochure.** A judge, a forensic auditor, or a SOC architect evaluating SIFTGuard for production deployment can `make spoliation-suite` and read the result. The trust surface is the test suite plus the schema files; no other artifact in the repository is load-bearing for the claim.

**The moat is orchestrator-agnostic.** None of the three controls depends on which of the five orchestrators (ADR-006) is in the loop. A LangGraph run, a Claude Code run, and a Native run all hit the same MCP boundary, write to the same append-only DB, and stamp the same methodology SHA. Changing the orchestrator changes none of the integrity properties — which is the precondition for the single-variable comparison ADR-006 depends on.

**Prompt drift is bounded.** A future prompt revision that loosens the "do not modify evidence" instruction does not change the system's spoliation behaviour. There is nothing in the prompt that the architecture relies on for integrity. The prompt can be inspected separately from the moat.

### 5.2 Negative

**Errata require new INSERTs, not edits.** A legitimate correction to a misreported IOC — an analyst realizes the C2 IP was misread — cannot be applied by editing the finding. The correction is a new INSERT with a `supersedes` pointer to the original row, and both rows remain visible in the audit DB. This is the correct legal behaviour and the wrong UX behaviour; operators will encounter friction.

**The append-only DB grows unboundedly.** Cases never shrink. Long-running tenants will face storage growth proportional to investigative activity. Operational mitigation is per-case database files with explicit retention policies, not VACUUMing live cases.

**Migration discipline is non-negotiable.** A developer who edits a migration file in place — instead of writing migration N+1 — breaks the startup integrity check and the service refuses to start. This is the intended behaviour; it is also a new failure mode for contributors unfamiliar with the convention.

### 5.3 Demands on Operators

A deployment of SIFTGuard inherits three commitments:

1. The audit DB is backed up before any retention action is taken; deletion is by file, not by SQL.
2. The methodology file is treated as a release-controlled artifact, not a configuration knob.
3. The tool catalog is regenerated as part of release builds, never edited by hand in production.

These commitments are surfaced as preflight checks at service start and documented in `LIMITATIONS.md` (T17).

---

## 6. Open Questions

**Q1 — Cross-case correlation.** The append-only DB is per-case. Cross-case IOC correlation (an attacker's C2 IP appearing in three unrelated cases) requires a query path across DBs that does not exist today. Adding it requires a read-only aggregation layer that respects per-case retention boundaries. Deferred.

**Q2 — Hardware-rooted attestation.** The strongest form of evidence integrity binds the audit DB to a TPM-signed boot chain — a SOC can prove not only that the DB was append-only but that it ran on the hardware claimed. SIFTGuard does not do this today. The architecture does not preclude it; the audit DB schema includes an `attestation_chain` column reserved for the receipt format.

**Q3 — Long-term key rotation for methodology SHA verification.** The methodology SHA is verified at run-time against the file on disk. A long-running deployment has no key-management story for revoking a compromised methodology version. Deferred post-hackathon.

---

## 7. References

- ADR-001 — Empirical evaluation framework (consumer of the audit DB)
- ADR-002 — Trace data model (the audit DB's logical schema)
- ADR-003 — Loop instrumentation (the `SnapshotWriter` that emits audit rows)
- ADR-006 — Multi-orchestrator architecture (single-variable comparison; depends on this moat)
- ADR-009 — Scorer source (audit-DB-mode scorer interface; consumes the same store)
- `tests/spoliation/` — 12-test suite that operationalizes the claim
- `docs/EVAL_FRAMEWORK.md` — Content-addressed methodology
- `docs/TOOL_CATALOG.md` — Auto-generated MCP surface (T22)

---

*The moat described here was implemented incrementally across T1–T15; this ADR formalizes the existing system, it does not propose new work.*
