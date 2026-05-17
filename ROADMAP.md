# SIFTGuard — 28-Task Master Roadmap
## Phase A — Empirical Foundation (T1–T8) ✅
- ✅ T1  Schema migration
- ✅ T2  Trace model + builder
- ✅ T3  Prompt v2 + output schema + validator
- ✅ T4  Loop instrumentation
- ✅ T5  Experiment runner + 8-config matrix
- ✅ T6  Analytics module — 6/7 panels live
- ✅ T7  EVAL_FRAMEWORK.md — Methodology v1.0.0
- ✅ T8  Methodology pinned — 7/7 tests, drift checker

## Phase B — Multi-Model + Multi-Orchestrator (T9–T10) ✅
- ✅ T9   Claude Code integration + DFIR CLAUDE.md
- ✅ T10  ADR-006 — Multi-orchestrator + vendor lock-in
  - Five orchestrators live: Native, LangGraph, OpenAI FC (gpt-5.5), Gemini 2.5 Pro, Claude Code
  - 144 passing tests at seal

## Phase C — Generalization (T11–T13) ✅
- ✅ T11   NIST CFReDS Hacking Case wired as TEST-002
- ✅ T12   Benchmark refactor — `--agent=` CLI flag + versioned ground truth
- ✅ T12.5 SCHARDT.img format conversion (E01 → raw dd / correct partition offset) — real TEST-002 F1
- ✅ T13   Protocol SIFT baseline run + delta publish

## Phase C.5 — UI Consolidation (T14) ✅
- ✅ T14  Two-mode dashboard (Results default / Run Live toggle)
  - 9 result panels: Accuracy, Models, Spoliation, IOC Graph (D3), Datasets, Orch Config, Evidence Chain, Eval, Limitations
  - Live Run: case header + Self-Correction Taxonomy + dark-terminal audit trail
  - Mock streaming fallback — 19 forensic events, metrics tick, status flips green
  - Tag: v1.19.2-task14-v2-merged-modes · 229 passing tests

## Phase D — Reviewer-Grade Docs (T15–T17)
- ⏳ T15  Backend wiring + ADR-007 + spoliation seed ← **ACTIVE**
  - Wire `launchInvestigation()` fetch → SSE stream → `pushTrail()` / metric counters / taxonomy state
  - ADR-007: audit-DB scorer interface stub (report-text scorer stays active path)
  - ADR-006 §generalization: document LangGraph/ClaudeCode 0.000 as tool config gap
  - Pre-demo seed: 3 real blocked mutation receipts in Panel 8
  - README "Known Limitations" section (mid-bottom placement)
- ⏳ T16  ADR gap-fill — ADR-003 (loop instrumentation), THREAT_MODEL.md (STRIDE + agent threats)
- ⏳ T17  LIMITATIONS.md — "When NOT to use SIFTGuard"

## Phase E — Production Engineering (T18–T22)
- ⏳ T18  CI/CD GitHub Actions — tests + spoliation suite + benchmark + coverage ≥80%
- ⏳ T19  Dockerfile + requirements.lock + `make demo` + 5-min cold-clone setup test
- ⏳ T20  Pydantic strict + mypy strict + ruff pinned, green in CI
- ⏳ T21  SBOM (syft) + signed v1.0.0-hackathon release tag
- ⏳ T22  Tool catalog auto-generation — JSON schemas → markdown tables

## Phase F — Communication (T23–T25)
- ⏳ T23  README hero rewrite pass 2 — open with multi-dataset numbers, embed figures
- ⏳ T24  Devpost final polish — quote ADR-006 §1 + §5.2, screenshots, media gallery
- ⏳ T25  Loom 2-min recording — orchestrator toggle, accuracy curve, ablation moment
  - Note: GitHub tag list is a portfolio artifact — use "engineering archaeology" line in script

## Phase G — Submission (T26–T28)
- ⏳ T26  Repo flip public — June 10 (MIT license, signed tag, release notes)
- ⏳ T27  Final cross-checks — cold clone, `make demo`, all links, CI green
- ⏳ T28  Submit Devpost — June 15 (ID: 1004826-siftguard)

## Permanently Dropped (with reason)
- ~~Disk-vs-memory correlation engine~~ — heavy infra, marginal signal
- ~~Persistent learning across runs~~ — bookkeeping cost > evidence value
- ~~Executive one-pager PDF~~ — wrong audience (CISO, not AI labs)
- ~~Deployment runbook~~ — only useful if SOC actually deploys
- ~~Customer decision matrix~~ — implicit in ADR-006
- ~~10-min architecture video~~ — Loom 2-min covers it
- ~~mkdocs site~~ — README + ADRs already do the work
- ~~Enterprise whitepaper~~ — wrong format for hackathon judges
- ~~LinkedIn cycle post~~ — strategy pivoted to deployment stories

## Highest ROI remaining (in order)
T15 → T18 → T23 → T19 → T16 → T24 → T25 → T26–T28