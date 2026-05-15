# ADR-008: Canonical Case Loader — Delete Flat Registry

**Date:** 2026-05-15  
**Status:** Accepted  
**Deciders:** Nafees Ahmad  
**Tag:** v1.17.1-t11-gaps-closed

---

## Context

Two parallel case registries existed after Task 11:

1. `src/siftguard/eval/datasets/registry.py` — a hardcoded Python dict mapping `case_id → DatasetMeta`. Added in Task 4 to support ablation experiments. Pydantic-typed but inline in source code.

2. `src/siftguard/cases/loader.py` + `experiments/cases/<CASE_ID>/manifest.json` — per-case JSON manifests loaded at runtime by a typed loader. Added in Task 11 to support TEST-002 (disk-only evidence with no memory image).

Having two registries violated the single-source-of-truth principle and created a silent failure mode: `DatasetMeta` assumed `memory_image` was always present, causing `evidence_available` to return `False` for any disk-only case. The benchmark CLI would silently skip TEST-002 without error.

---

## Decision

Delete `datasets/registry.py`. `cases/loader.py` is the canonical source of truth for all case metadata.

Public API:
```python
from siftguard.cases.loader import get_case, list_cases, list_case_ids, evidence_paths
```

---

## Rationale

**1. Manifest-per-case scales; dict-in-source does not.**  
Adding TEST-003 requires one new JSON file. The flat registry required editing Python source, bumping imports, and re-running tests to catch regressions.

**2. Manifests encode tool availability explicitly.**  
`CaseManifest.available_tools` / `unavailable_tools` lets the MCP server and scorer filter IOC expectations by evidence surface at load time — not at runtime guess. This is the contract that makes TEST-002 (disk-only) and TEST-001 (memory-only) comparable on the same benchmark without special-casing.

**3. TEST-002 is the proof case.**  
The flat registry could not represent a disk-only case cleanly. The manifest for TEST-002 lists `volatility_*` tools under `unavailable_tools` with `reason: no_memory_image`. The scorer reads this and filters ground-truth IOCs with `evidence_location: memory_only` — preventing false negatives from un-reachable IOCs inflating the miss rate.

**4. Silent failure → loud failure.**  
`SnapshotWriter.__init__` now raises `RuntimeError` if `experiment_run` table is missing, referencing the exact migrate command. The flat registry's `evidence_available` returned `False` silently and let the benchmark proceed with no evidence, producing meaningless scores.

---

## Consequences

- `datasets/registry.py` deleted in commit `refactor(adr-008)` — 168 tests green after migration.
- All call sites migrated via automated Python rewrite (no manual edits).
- `TEST-001.json` and `TEST-002.json` manifests are now the ground truth for tool availability and evidence paths.
- T12 benchmark refactor builds on `list_case_ids()` as the authoritative case enumeration — no hardcoded lists anywhere in the benchmark CLI.
- Adding a third dataset (T11 stretch goal or post-hackathon) is a single manifest file + ground truth JSON.

---

## Alternatives Considered

**Keep flat registry, add disk_image field** — rejected. Would require adding special-case logic for every new evidence type. Manifests are open-schema by design.

**Delete both, use env vars** — rejected. Env vars are not version-controlled and break reproducibility, which is the core claim of the spoliation moat.