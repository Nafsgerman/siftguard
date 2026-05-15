# Ground Truth Schema v1.1.0

## Change vs v1.0.0
Adds required `evidence_location` per IOC. Enables per-case scoring honesty when an evidence shape (memory or disk) is absent.

## IOC schema (additive)
```json
{
  "ioc_id": "ioc-net-c2-metasploit-2240",
  "ioc_type": "network_connection",
  "expected": {
    "remote_ip": "108.79.235.64",
    "remote_port": 33000,
    "process_pid": 2240
  },
  "confidence_threshold": 0.75,
  "evidence_location": "memory_only",   // NEW: "memory_only" | "disk_only" | "both"
  "rationale": "C2 channel visible only in process/network memory artefacts"
}
```

## Enum semantics
- `memory_only` — IOC only discoverable via memory analysis (process list, netscan, malfind, handles, etc.)
- `disk_only` — IOC only discoverable via disk artefacts (MFT, registry hives, filesystem walk, file content)
- `both` — IOC has corroborating evidence on both surfaces; either reachable tool can confirm

## Scoring contract
- Per-case scorer computes `applicable_iocs = [ioc for ioc in ground_truth if reachable(ioc, case_manifest)]`
- `composite_score = hits / len(applicable_iocs)` — denominator is applicable, not total
- Unreachable IOCs land in `score_breakdown.not_applicable[]` with the reason; never counted as miss
- TEST-001 composite stays mathematically identical to v1.0.0 (100% applicability)

## Migration
- v1.0.0 files remain untouched (historical record)
- v1.1.0 siblings created for every case: `TEST-001-v1.1.0.json`, `TEST-002-v1.1.0.json`
- Default backfill for TEST-001: `memory_only` unless IOC references a filesystem path → `both`
- Scorer reads `--ground-truth-version` flag (default v1.1.0)

## ADR linkage
ADR-007 (spoliation moat) gains sibling property: **typed tool absence**. Tool capabilities are Pydantic types resolved at case-load time, not runtime hopes. Same root architectural commitment as the spoliation contract.