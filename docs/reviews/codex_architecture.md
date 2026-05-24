# SIFTGuard Code-Level Architecture Review

This document contains a code-level architectural review of `src/siftguard/orchestrators/`, `src/siftguard/mcp_server/`, and `src/siftguard/models/`. It identifies three high-priority refactoring targets for the next sprint and analyzes the single biggest architectural risk in the orchestrator-to-MCP boundary.

---

## 1. Abstractions to Refactor in the Next Sprint

### Refactor 1: Shotgun Parameterization in `BaseOrchestrator`
* **File and Function Name:** `src/siftguard/orchestrators/base.py` -> `BaseOrchestrator.run_case`
* **The Smell:** **Shotgun Parameterization.** The interface requires nine separate positional/keyword arguments just to invoke a case run, locking the core orchestration process into a fragile and non-extensible contract.
* **The Refactor:** Encapsulate all execution, runtime, telemetry, and debugging parameters into a single unified `InvestigationContext` or `CaseConfig` Pydantic model. This model will hold configurations for the case briefing, evidence file mappings, path locations, model names, ground truth parameters, and runtime flags. The protocol method signature will then be simplified to `async def run_case(self, context: InvestigationContext) -> tuple[str, str]`, ensuring that adding or modifying execution flags in future sprints only requires updating the data model rather than modifying the signature across the base class and all five adapter implementations.
* **Risk of Leaving As-Is:** **High.** Adding new features (such as token budget caps, model temperature overrides, caching controls, or runtime credentials) will trigger breaking signature changes across the entire multi-orchestrator pipeline, severely slowing down engineering velocity.

### Refactor 2: Hardcoded Schemas and Monolithic Tool Dispatch in `server.py`
* **File and Class/Function Name:** `src/siftguard/mcp_server/server.py` -> `TOOLS` static list and `DISPATCH` dictionary.
* **The Smell:** **Missing Abstraction / Shotgun Surgery.** The MCP server manually defines its entire tool catalog and JSON-Schema parameters inside a static list and uses a hardcoded dictionary mapping for tool execution.
* **The Refactor:** Implement a dynamic `Registry` abstraction using decorators to let forensic tools self-register their schemas, documentation, and executors directly from their implementation files (e.g., `@registry.tool(name="vol_pslist")`). At server startup, the registry will dynamically compile Pydantic models into the correct JSON-Schemas that the MCP framework requires. This decouples the transport layer (stdio stdio-server) from individual forensic tools (Volatility, RegRipper, TSK), keeping the codebase modular.
* **Risk of Leaving As-Is:** **Medium.** Adding, removing, or refactoring forensic tools requires changing code in three non-contiguous places (the imports, the static `TOOLS` list, and the `DISPATCH` dictionary), dramatically increasing schema-mismatch and integration bugs.

### Refactor 3: Three Disjoint Taxonomies for Telemetry Event Classification
* **File and Class/Function Name:** `src/siftguard/models/correction_taxonomy.py` -> `SelfCorrectionType` / `classify_correction`
* **The Smell:** **Leaky Abstraction & Inconsistent Domain Model.** The application manages three completely disjoint, overlapping taxonomies for the same event category: `SelfCorrectionType` in `models` (e.g., `FORMAT_RETRY`), the LLM-prompted output schema in `v2.txt` (`tool_failure_recovery`, `hypothesis_revision`), and the SQL database triggers (`promote`, `demote`, `replace`, `abandon`).
* **The Refactor:** Consolidate these three distinct representations into a single strongly-typed `InvestigationEvent` domain model that defines clear conversion, validation, and serialization rules. Prompt parsers, SQLite database insert hooks, and dashboard telemetry analytics will then consume this unified class as the single source of truth, replacing the brittle substring keyword matching (`classify_correction`) currently used to render the self-correction taxonomy on the dashboard.
* **Risk of Leaving As-Is:** **Medium.** Telmetry visualizations and evaluation benchmarks will suffer from data quality drift, resulting in inaccurate self-correction tracking and fragile parsing errors whenever the model output deviates slightly from the keyword-heuristic lists.

---

## 2. The Single Biggest Architectural Risk in the Orchestrator-to-MCP Boundary

The single biggest architectural risk is the **complete lack of OS-level process and privilege isolation between the Orchestrators and the MCP Server.**

Because SIFTGuard runs as a local application on the SIFT Workstation under the same user privileges (e.g., `sansforensics`), **the MCP boundary is a logical interface, not a security boundary.** 

If a malicious prompt injection or model jailbreak occurs—especially when running interactive or shell-executing adapters like `siftguard-claudecode`—the LLM is not restricted to calling the "read-only" MCP tool catalog. Because the orchestrator and the MCP server share the same process environment and write-permissions to the evidence directories, a compromised agent can execute standard Python or Bash commands to:
1. Modify or delete the raw evidence images directly.
2. Disable, drop, or rewrite the SQLite database file and its triggers.
3. Tamper with the committed ground truth or local cache files.

A true "spoliation moat" requires **hard security boundaries** at the operating system level: the orchestrator must execute in an isolated, zero-privilege container or non-privileged user sandbox with zero direct filesystem write-access to `/cases/` or the case database, leaving the independent, privileged MCP server process as the *only* component authorized to execute reads on the evidence files and write-appends to the case SQLite database.
