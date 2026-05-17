# SIFTGuard — Known Limitations

Version: 1.0  
Date: 2026-05-17  
Relates to: [THREAT_MODEL.md](THREAT_MODEL.md), [ADR-006](adr/ADR-006-multi-orchestrator-vendor-lockin.md)

This document describes the operational boundaries of SIFTGuard v1.x. It is intended
for forensic practitioners, security engineers, and evaluators considering deployment.
Honest scope definition is a security property: a tool that overstates its capabilities
is a liability in evidentiary contexts.

---

## 1. Evidence Format Constraints

**SIFTGuard is validated against raw memory images (`.img`, `.raw`, `.mem`).**

Volatility 3 supports a wide range of formats, but SIFTGuard's MCP tool layer and
benchmark suite were developed and validated against the SANS SRL-2018 dataset
(Windows 7 x64 memory image, TEST-001) and the NIST CFReDS SCHARDT case (TEST-002).

| Format | Status |
|---|---|
| Raw memory image (`.img`, `.raw`) | ✓ Validated |
| E01 / Expert Witness Format | ⚠ Requires conversion to raw (`ewfexport`) |
| VMEM / VMware snapshot | ⚠ Untested — may work with correct Volatility profile |
| Hibernation file (`hiberfil.sys`) | ⚠ Untested |
| Live memory acquisition | ✗ Not supported — SIFTGuard requires a static image |
| Network packet captures (`.pcap`) | ✗ Out of scope |

**Implication:** Running SIFTGuard against an unsupported format will produce tool
errors, not forensic findings. The agent will terminate with `terminated_reason="error"`
and zero F1 score. This is a tool configuration gap, not a reasoning failure
(see ADR-006 §generalization-gap).

---

## 2. Operating System Coverage

SIFTGuard's Volatility plugin set targets **Windows memory images exclusively**.

Plugins used: `windows.psscan`, `windows.netscan`, `windows.malfind`,
`windows.mftscan.MFTScan`, `windows.mftscan.ADS`, `windows.registry.printkey`.

Linux and macOS memory forensics require a different plugin set and ground truth.
Neither is present in the current benchmark suite. An agent run against a Linux image
will produce Volatility errors; the agent loop will retry, exhaust its iteration budget,
and terminate without findings.

---

## 3. Hallucination Rate

**LLM-based agents can fabricate IOCs.**

Every IOC in the final report is traceable to a Volatility plugin output row stored in
`iteration_snapshot.findings_so_far`. This provides *output-level* provenance: you can
verify that the agent claimed to find a value. It does not provide *field-level*
provenance: it does not prove the value was *derived* from evidence rather than
*coincidentally matching* it.

The F1 benchmark score against ground truth is the primary hallucination guard. A
high F1 score means the agent's findings closely match expert-verified IOCs, but it
does not eliminate the possibility of a lucky hallucination that happens to match.

**Guidance:** Do not use SIFTGuard output as the sole basis for attribution or legal
action. It is a triage tool, not a substitute for analyst review.

---

## 4. Soft Timeouts

**Volatility plugin timeouts are advisory, not enforced at the OS level.**

The agent loop enforces a per-iteration wall-clock timeout. When exceeded, the loop
logs a timeout event and terminates the iteration. However, the underlying Volatility
subprocess is not sent `SIGKILL` — it continues running in the background.

On the SANS SIFT VM (4-core x86_64, 8GB RAM emulated via UTM), this is acceptable
because Volatility plugin runtimes on a 5GB image are bounded by physical I/O speed.
In a resource-constrained or production environment, a malformed image could cause
orphaned Volatility processes to accumulate and exhaust available memory.

**Mitigation (planned):** Hard `SIGKILL` on the Volatility subprocess after timeout
deadline + grace period.

---

## 5. Audit Trail: Convention-Only Append-Only Enforcement

**The `iteration_snapshot` and `hypothesis_event` tables are append-only by
application convention, not by database constraint.**

`SnapshotWriter` exposes no `UPDATE` or `DELETE` methods. However, direct SQL access
to the `.db` file bypasses this entirely. An analyst with shell access to the SIFT VM
can modify audit rows without detection.

The `blocked_mutation` table records attempts blocked at the application layer, but
it cannot record modifications made directly via `sqlite3` CLI or any other tool that
bypasses `SnapshotWriter`.

**Planned hardening:**
- SQLite `BEFORE UPDATE` / `BEFORE DELETE` triggers raising errors on protected tables
- SHA-256 chain hash: each `iteration_snapshot` row hashes its content + the prior
  row's hash, making silent modification detectable without a trusted timestamp server

Until these controls are in place, SIFTGuard's audit trail satisfies *investigative
reproducibility* (you can replay what the agent did) but not *tamper-evidence*
(you cannot cryptographically prove it was not modified post-hoc).

---

## 6. Concurrency

**SIFTGuard supports multiple cases in parallel, but not multiple agents per case.**

Two simultaneous agent runs against the same `case_id` will produce interleaved
`iteration_snapshot` rows. The benchmark scorer reads snapshots by `run_id`, so F1
computation remains correct, but the Panel 7 dashboard renders per-case views and
will show interleaved findings without a clear per-run boundary.

**Supported:** `agent_A --case TEST-001` + `agent_B --case TEST-002` simultaneously  
**Unsupported:** `agent_A --case TEST-001` + `agent_B --case TEST-001` simultaneously

---

## 7. Orchestrator Generalization Boundary

**The orchestrator-agnostic claim is bounded by tool path resolution.**

All five orchestrators (Native, LangGraph, OpenAI FC, Gemini 2.5 Pro, Claude Code)
demonstrate equivalent reasoning quality when given valid tool output. They differ in
cost (4.72× spread, documented in ADR-006 §5.2) and latency, not in forensic accuracy.

However, LangGraph and Claude Code adapters resolved tool paths from a module-level
constant in early versions. This caused 0.000 F1 on TEST-002 until `case_id` was
injected at adapter construction time. Any orchestrator adapter that hardcodes evidence
paths will fail silently on new datasets.

**Guidance:** When adding a new dataset, run `--dry-run` with each orchestrator adapter
and verify tool call arguments before committing a benchmark run.

---

## 8. Model Availability and Cost

SIFTGuard makes live API calls to Anthropic, OpenAI, and Google during benchmark runs.

- API outages in any provider will cause the corresponding orchestrator to terminate
  with `terminated_reason="error"` and zero F1 for that run.
- Token costs are non-trivial on a 5GB image. A full five-orchestrator benchmark run
  against TEST-001 costs approximately $2–6 USD depending on iteration depth.
- `gpt-5.5` does not accept a `temperature` parameter. Passing one raises a 400 error.
  The OpenAI FC adapter omits `temperature` by design.

---

## 9. What SIFTGuard Is Not

| Capability | Status |
|---|---|
| Real-time / live memory forensics | ✗ Static images only |
| Disk forensics (filesystem analysis without Volatility) | ✗ Out of scope |
| Network forensics (PCAP analysis) | ✗ Out of scope |
| Legal-grade chain-of-custody without additional controls | ✗ See §5 |
| Multi-OS support (Linux, macOS memory) | ✗ Windows only in v1.x |
| Unsupervised production deployment without analyst review | ✗ Triage tool only |
| Persistent learning across runs | ✗ Explicitly excluded (bookkeeping cost > value) |

---

## 10. Reporting Issues

Limitations that affect benchmark reproducibility should be filed as GitHub issues with
the label `reproducibility`. Limitations that affect evidentiary integrity should be
filed with the label `audit-integrity`.

Repo: https://github.com/Nafsgerman/siftguard