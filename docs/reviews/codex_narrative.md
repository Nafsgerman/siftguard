# SIFTGuard Devpost Narrative Pressure-Test Review

This document contains a senior-level pressure-test of SIFTGuard's Devpost submission narrative (`SUBMISSION.md`) and Loom demo script (`loom_script.md`). It evaluates the accuracy of system claims against the repository code, reframes marketing language into rigorous engineering descriptions, suggests credible challenges to add, and exposes gaps in the Loom script demo flow.

---

## 1. Unbacked or Inaccurate Narrative Claims

### Claim A: Database-Level Trigger Enforcement
* **Narrative Quote:** `"Append-only audit DB. SQLite with insert-only access enforced at the data layer. Migrations versioned and verified at startup."` (`SUBMISSION.md`, line 73)
* **The Reality:** **This claim is completely unbacked by the codebase.** The README ("Audit trail is append-only by convention, not by DB constraint") and the Threat Model (§3.4) admit that `BEFORE UPDATE` and `BEFORE DELETE` triggers do not exist in the SQLite schema and are deferred post-hackathon. Enforcement is done entirely in the Python application's `SnapshotWriter` class. Anyone with shell access to the workstation can directly delete or overwrite database rows using standard `sqlite3` commands.
* **Remediation:** Remove the claim of "enforced at the data layer" and reframe it as "enforced at the application-layer writer."

### Claim B: Complete Architectural Spoliation Moat
* **Narrative Quote:** `"Spoliation test suite: 12/12 attacks blocked architecturally at the MCP layer — not by prompt"` (`SUBMISSION.md`, line 92)
* **The Reality:** The 12-test suite passes, but it does *not* verify a complete architectural moat. The path validation in `safe_exec.py` contains a severe vulnerability: it only checks paths if they explicitly start with `/` or `./`. Relative paths starting with `..` (e.g. `../../etc/passwd` or `../../cases/`) skip the validation check entirely, permitting path-traversal escapes. The architecture does *not* block relative path traversal.
* **Remediation:** Fix the path validation regex in `safe_exec.py` to cover all relative path formats before claiming complete architectural spoliation resistance.

### Claim C: Zero Hallucinated Findings Proof
* **Narrative Quote:** `"Zero hallucinated findings — every claim traces to an audit DB row."` (`SUBMISSION.md`, line 238)
* **The Reality:** While every reported finding should map to a tool call ID, SIFTGuard does *not* actually enforce field-level provenance (proving the finding literal was extracted from the raw bytes of the tool response, as admitted in `LIMITATIONS.md`). The agent can still hallucinate an IP or a process name that coincidentally matches the ground truth.
* **Remediation:** Downgrade the claim from "zero hallucinated findings" to "all reported findings are mapped to a specific tool execution ID in the audit trail to ensure traceability."

---

## 2. Reframing Marketing as Rigorous Engineering

### marketing -> engineering reframes:

1. **Quote:** `"The gap is real: adversaries move at machine speed. Defenders don't. SIFTGuard closes that gap."` (`SUBMISSION.md`, line 37)
   * **Engineering Reframe:** *"SIFTGuard automates the correlation, sequencing, and analysis of memory and disk forensics on a SIFT Workstation, reducing triage latency from hours of manual CLI analysis to a 100-260s automated pipeline."*
2. **Quote:** `"Court-defensible by design — SBOM signed with Sigstore keyless; SLSA Level 3 build provenance"` (`SUBMISSION.md`, line 96)
   * **Engineering Reframe:** *"Ensures supply-chain integrity for the deployment VM image using Sigstore keyless signatures and SLSA Level 3 build verification, ensuring the virtual machine package is tamper-evident."*
3. **Quote:** `"The system prompt is defense-in-depth. The architecture is the wall."` (`loom_script.md`, line 69)
   * **Engineering Reframe:** *"The custom MCP server acts as an isolation boundary by exposing only a fixed, version-pinned read-only API of approved forensic tools, moving safety enforcement from soft prompt instructions to hard typed execution wrappers."*

---

## 3. Increasing the Credibility of the "Challenges" Section

The current challenges list safe, easily resolved engineering blocks (e.g., matching schemas, dataset offsets). To maximize credibility, SIFTGuard should add a **real architectural challenge**:

### Hard Challenge to Add: SQLite Concurrency and Thread-Lock Contention
> **Upstream API Non-Determinism and DB Write Contention:** Implementing a synchronous, per-iteration `SnapshotWriter` across five parallel orchestrators caused severe SQLite write locks (`SQLITE_BUSY` errors). Because SQLite locks the entire database file during writes, parallel benchmarking threads frequently blocked the forensic tool loops. Resolving this required implementing custom exponential-backoff sleep-retry loops at the database seam to guarantee that telemetry recording did not drop data or bottleneck the execution speeds.

---

## 4. Loom Script Gaps vs. Live Demo Reality

* **Multi-Orchestrator Comparison:** Frame 2 states, `"Select Native Loop. Dashboard re-binds to that adapter's cached run."` This reveals to the judge that the dashboard is not running the orchestrators *live* during the demo, but is instead loading pre-computed cache files. If a judge asks to run a live comparison on a fresh case, they will witness the substantial latency (100–260s wall clock time) and the potential Volatility timeout hangs.
* **The Unverified Spoliation Test:** Frame 4 shows running `pytest tests/spoliation/test_spoliation.py` to prove the spoliation moat. However, a technical judge reviewing the test file will see that it only validates a hardcoded list of command strings (like `"/etc/passwd"`). The test suite fails to test relative path escapes (`../../etc/passwd`), concealing the path-traversal vulnerability in the MCP server's safe executor.
* **Brittle Telemetry Classification:** The "Self-Correction Taxonomy" shown in the dashboard is not mapped to structured database entities; it relies on keyword substring heuristics (`classify_correction` in `models/correction_taxonomy.py`). Any slight variation in the model's explanation format will break the dashboard's rendering, which is not apparent in the Loom script's polished sequence.
