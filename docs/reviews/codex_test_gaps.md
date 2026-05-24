# SIFTGuard Test Gap Scan

This document contains a professional test gap scan of `src/siftguard/` and `tests/`. It identifies the three highest-risk untested or under-tested code paths in the repository and provides concrete test scenarios to remediate them.

---

## 1. High-Risk Test Gaps in SIFTGuard

### Gap 1: Relative Path-Traversal Vulnerability in `safe_exec` Path Validation
* **File and Class/Function:** `src/siftguard/mcp_server/safe_exec.py` -> `safe_exec` function
* **Why it is High-Risk:** **Security Boundary & Evidence Integrity.** The function prevents directory escape only if the path argument literally starts with `/` or `./`. An attacker or a jailbroken model can bypass this check completely by passing a relative path starting with `..` (e.g., `../../etc/passwd` or `../../cases/TEST-002/secrets.txt`), exposing files outside the evidence directory.
* **Specific Test Case to Add:**
  * **Scenario:** Mock a call to `safe_exec` using an allowed binary (e.g., `fls`) and pass arguments containing relative path traversals that do not start with a slash or dot-slash, such as `["-r", "cases/../secrets.txt"]` or `["../../etc/passwd"]`.
  * **Assertion:** Assert that a `SafeExecError` is raised with a message matching `path escapes evidence root`.
  * **What it would catch:** This test would fail under the current code structure, immediately exposing a major path-traversal vulnerability that allows models to access raw workstation system files.

### Gap 2: SQLite Database Append-Only Enforcement at the Storage Layer
* **File and Class/Function:** `src/siftguard/audit/log.py` (or the migration setup verifying table triggers)
* **Why it is High-Risk:** **Evidence Integrity & Chain of Custody.** SIFTGuard’s ADR-007 claims that the audit database is protected from post-hoc tampering by database-level triggers (`BEFORE UPDATE` and `BEFORE DELETE` triggers raising `ABORT`). However, `README.md` and `THREAT_MODEL.md` both disclose that this is a known gap and that the triggers are not implemented at the database layer.
* **Specific Test Case to Add:**
  * **Scenario:** Open a direct SQLite connection to the case database (e.g., `audit/TEST-001.db`) using the standard library `sqlite3` driver—bypassing the application's `SnapshotWriter` class—and attempt to execute an `UPDATE` or `DELETE` query (e.g., `DELETE FROM hypothesis_event` or `UPDATE iteration_snapshot SET cost_usd = 0.0`).
  * **Assertion:** Assert that the SQLite engine aborts the write transaction and raises a `sqlite3.OperationalError` with the message `'append-only'`.
  * **What it would catch:** Under the current repository status, this test would pass (i.e. allow the deletion/modification to succeed), exposing that the system's "tamper-proof" evidence claim is an application-level convention rather than a hard database-level constraint.

### Gap 3: Timeout Recovery & Connection Cleanup in the Orchestrator Loops
* **File and Class/Function:** `src/siftguard/agent/loop_v2.py` (or `siftguard/agent/loop.py`) -> Loop execution functions
* **Why it is High-Risk:** **Orchestrator Failure Modes & Database Concurrency.** If an LLM call or a Volatility subprocess hangs or times out, the orchestrator must terminate gracefully. If it crashes without writing a final state or closing its database connection, it leaves open transaction locks, corrupting subsequent benchmark runs.
* **Specific Test Case to Add:**
  * **Scenario:** Initialize an agent loop and mock the HTTP/API client (`google-genai` or `anthropic` client) to raise a `TimeoutError` or mock an MCP tool dispatch to hang indefinitely during the second loop iteration.
  * **Assertion:** Assert that the loop terminates gracefully, writes a final row to the database with `terminated_reason = "error"`, records the elapsed duration, and cleanly closes the `SnapshotWriter` connection.
  * **What it would catch:** It would identify cases where a timeout triggers an unhandled traceback that crashes the script mid-execution, leaving the database file locked in a dirty state and preventing the dashboard from loading subsequent cases.
