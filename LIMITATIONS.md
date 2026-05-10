# Limitations

SIFTGuard is a hackathon-scoped prototype with deliberately narrow validation. This document states what was measured, what wasn't, and where the published numbers stop being meaningful. It exists because most LLM-agent demos don't have one, and that absence is itself a finding.

## What we validated

| Claim | Evidence |
|---|---|
| 0.909 IOC F1 on TEST-001 | 6 seeded runs, σ = 0.000 |
| Self-correction stabilizes seed variance | 24-run ablation, 8 configurations |
| Spoliation impossibility | 12/12 automated tests in `tests/spoliation/` |
| Methodology immutability | SHA-256 pin checked in CI |
| Hallucination verification mechanism | `verify_finding()`, 60/60 unit tests |

## What we did not validate

### Cross-case generalization
Validation was performed on a single memory image: SRL-2018 TEST-001. TEST-004 and TEST-005 cache warm-up did not complete in submission window due to Volatility execution time on UTM-emulated x86 hardware. Until those runs land, **no claim about generalization to unseen APT scenarios is supported by evidence in this repo.** A 0.909 F1 on one image is one image.

### Hallucination rate in production traffic
The verifier mechanism is tested (60/60). The rate at which the agent actually hallucinates in live runs is not yet measured end-to-end — verification fires post-hoc, but the integration into the agent loop's report-time path is incomplete. Panel 8 will populate that data once wired.

### Adversarial robustness
The MCP server is typed and the spoliation tests cover known evasion patterns. They do not cover novel adversarial inputs, prompt injection in evidence content, or memory-image tampering designed to defeat the typed boundary specifically. No red-team pass has been performed.

### Multi-model vendor risk
Headline numbers are from Claude Sonnet 4.6 only. Equivalent runs against GPT-4o, Opus, Haiku, and Gemini 2.5 Pro are scoped in the roadmap (Phase B) but not executed. Vendor-lock claims would be premature.

### Scale
Validation memory image is ~3 GB. Real DFIR engagements routinely involve 32 GB, 64 GB, and full disk acquisitions. Performance characteristics at that scale are not measured. The cache layer assumes plugins complete; on larger images they may not.

### Methodology of the IOC scorer
IOC matching uses substring lookup against ground truth, not semantic equivalence. An agent reporting `172.16.4.10` matches; reporting `the C2 server at 172.16.4.10:8080` matches; reporting `the C2 IP we identified` does not. This favors agents that emit raw indicators and penalizes agents that summarize. The choice is documented; whether it's the right choice for forensic tooling specifically is open.

### Statistical power
n = 6 seeds on the headline config. Bootstrap confidence intervals are reported, but with that sample size the σ = 0.000 finding is best read as "no observed variance" rather than "provably zero variance." A 30-seed run would tighten this. Cost-bounded.

## Known design tradeoffs

- **Memory-only analysis path.** No `$MFT` artifact present in TEST-001; the MFT tool runs against memory plugins (`windows.mftscan.MFTScan`, `windows.mftscan.ADS`) rather than parsed disk MFT. This was the right call for this image; it would not be for a disk-acquisition workflow.
- **Cache layer is a demo affordance.** Volatility outputs cached at `/cases/TEST-001/siftguard_cache/` so the agent runs in seconds instead of timing out under emulation. In a production deployment the cache becomes a staleness risk and would need invalidation logic.
- **Single orchestrator.** The agent loop is custom. LangGraph and OpenAI function-calling adapters are designed but not implemented. Vendor-portability claims are aspirational.
- **No human-in-the-loop UI.** The dashboard streams findings and audit entries but does not surface a "this looks wrong" override path for analysts. Production DFIR tooling needs that.

## What this means for the reader

If you are a SANS judge: the 0.909 number is real, on this image, with the methodology stated. The architectural claims (typed MCP, spoliation impossibility, audit chain) are independent of the accuracy number and stand on their own tests.

If you are evaluating SIFTGuard for procurement: don't. This is a hackathon prototype. The next steps that would make it procurement-relevant are listed in the roadmap; none are shipped.

If you are reviewing the candidate behind this repo: the hero number is one image. The `LIMITATIONS.md` file is the actual interview signal.

## Roadmap to closing these gaps

| Limitation | What closes it | Status |
|---|---|---|
| Single-case validation | TEST-004/005 baseline runs | Cache warm in progress |
| Hallucination rate not measured | Verifier wired into agent loop end-to-end | Mechanism shipped, integration pending |
| Adversarial robustness | Red-team pass on typed MCP boundary | Not started |
| Multi-model vendor risk | Phase B matrix runs | Designed, not run |
| Scale | 32 GB image benchmark | Not started |
| Scorer methodology | Semantic-equivalence option | Not started |

This document will be updated as items close. Last update: 2026-05-09.