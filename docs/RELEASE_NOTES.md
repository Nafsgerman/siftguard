# SIFTGuard v1.0.0-hackathon

> Autonomous DFIR agent — real APT malware found in a forensic memory image with a single command, zero analyst input.

## TL;DR

| Metric | Value |
|--------|-------|
| Orchestrators compared | 5 (Native, LangGraph, OpenAI FC, Gemini 2.5 Pro, Claude Code) |
| Tests passing | 270 |
| mypy | strict, 0 errors |
| ruff | 0.15.13 pinned, 0 violations |
| SBOM | Unfiltered SPDX 2.3 + CycloneDX 1.5, cosign-signed |
| Datasets | SRL-2018 (TEST-001) + NIST CFReDS (TEST-002) |

**Reproduce in 5 minutes:**
```bash
git clone https://github.com/Nafsgerman/siftguard && cd siftguard && make demo
```

**Verify the SBOM signature:**
```bash
cosign verify-blob \
  --bundle sbom.spdx.json.bundle \
  --certificate-identity-regexp 'https://github.com/Nafsgerman/siftguard/.github/workflows/release.yml' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  sbom.spdx.json
```

## Architecture

SIFTGuard runs on a SANS SIFT Workstation VM with a Pydantic-typed Custom MCP Server, a
self-correcting agent loop, and an append-only SQLite audit trail. Five orchestrator paradigms
are isolated as the single variable against identical MCP tools and model weights.

**Key ADRs:**

| ADR | Decision |
|-----|----------|
| [ADR-001](docs/adr/ADR-001-empirical-evaluation-framework.md) | Empirical evaluation framework |
| [ADR-006](docs/adr/ADR-006-multi-orchestrator-vendor-lockin.md) | Multi-orchestrator design + vendor lock-in |
| [ADR-007](docs/adr/ADR-007-spoliation-moat.md) | Append-only spoliation moat |

Orchestrator cost spread: **4.72×** across five paradigms (ADR-006 §5.2). Volatility 3 runs
against a 5 GB memory image with a file-based cache at `/cases/TEST-001/siftguard_cache/`
to prevent timeout on emulated x86.

## Production Engineering

- **Pydantic strict=True** on `EvidencePath` + `SelfCorrectionEvent`; coercion-required models
  explicitly deferred with inline rationale
- **17 scoped `# type: ignore[code]`** annotations; zero module-level exemptions
- **Unfiltered SBOM** — full transitive supply-chain inventory, not a marketing artifact
- **SLSA L3** build provenance via `actions/attest-build-provenance@v1`; signatures bound to
  the workflow run SHA, not a developer key
- **CI**: ruff → mypy → pytest → benchmark on every push to main

## Verification

```bash
# Tests
python3 -m pytest tests/ -x -q

# Type + lint
python3 -m mypy src/ && python3 -m ruff check src/ tests/

# SBOM structure
python3 -m pytest tests/release/test_sbom_artifacts.py -v

# Signature (requires bundles from release assets)
make sbom-verify
```

## Known Limitations

See [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md). Critical items:

- Requires Volatility 3 + SIFT Workstation VM for full forensic tool access
- Claude Code orchestrator rows show empty IOC graph (missing `ioc_detected` event emission) —
  flagged in Panel 7 dashboard, out of scope for this release
- Coverage floor at 38%; Phase E target of 80% is a tracked carry-forward

## What's Not in Scope

- Disk-based forensics (MFT scaffolded, not end-to-end)
- Cross-session learning persistence
- Production SOC deployment runbook

---

_SANS FIND EVIL! Hackathon · June 2026 · MIT License_
