# SIFTGuard — 36-Task Master Roadmap

## Phase A — Empirical Foundation
- ✅ 1.1 Schema migration
- ✅ 1.2 Trace model + builder
- ✅ 1.3 Prompt v2 + output schema + validator
- ✅ 1.4 Loop instrumentation
- ✅ 1.5 Experiment runner + 8-config matrix
- ✅ 1.6 Analytics module — 6/7 panels live
- ✅ 1.7 EVAL_FRAMEWORK.md — Methodology v1.0.0
- ✅ 1.8 Methodology pinned — 7/7 tests, drift checker
- ✅ 1.9 README hero rewrite + Devpost draft + architecture-v3.svg
- ✅ 2 Self-correction event taxonomy
- ✅ 3 Hallucination verifier — verify_finding(), Panel 8, 60/60 tests
- ⏳ 4 Ablation matrix — TEST-004/005 generalization + 3-seed repeats
- ⏳ 5 ADR-001 — "Why empirical eval was necessary"

## Phase B — Multi-Model + Multi-Orchestrator
- ⏳ 6 LangGraph orchestrator adapter
- ⏳ 7 OpenAI function-calling adapter
- ⏳ 8 Multi-model vendor-risk matrix (Sonnet/Opus/Haiku/GPT-4o/Gemini) → Panel 7
- ⏳ 9 Claude Code integration + DFIR CLAUDE.md
- ⏳ 10 ADR-006 — Multi-orchestrator + vendor lock-in

## Phase C — Multi-Source + Community Benchmark
- ⏳ 11 Paired disk + memory dataset (NIST CFReDS or DFRWS 2008)
- ⏳ 12 Real disk-vs-memory correlation engine
- ⏳ 13 Community benchmark refactor (--agent= CLI flag, versioned ground truth)
- ⏳ 14 Protocol SIFT baseline run + delta publish
- ⏳ 15 Persistent learning across runs (progress.jsonl + improvement curve)

## Phase D — Enterprise / TDL Differentiators
- ⏳ 16 Full ADR set (ADR-002 through ADR-009)
- ⏳ 17 THREAT_MODEL.md — STRIDE + deployment threat model
- ⏳ 18 LIMITATIONS.md — "When NOT to use SIFTGuard"
- ⏳ 19 Executive one-pager PDF (CISO-facing)
- ⏳ 20 Reference deployment runbook — "SOC deploy in 4 hours"
- ⏳ 21 Customer decision matrix (model x orchestrator x iteration cap)
- ⏳ 22 Architecture review video (10 min, decision-tree walkthrough)

## Phase E — Production Engineering
- ⏳ 23 CI/CD — GitHub Actions (tests + benchmark + spoliation suite + coverage ≥80%)
- ⏳ 24 Reproducibility — Dockerfile, requirements.lock, make demo, 5-min setup test
- ⏳ 25 Pydantic strict + mypy strict + ruff pinned in CI
- ⏳ 26 mkdocs-material docs site → GitHub Pages
- ⏳ 27 SBOM + signed v1.0.0-hackathon release tag
- ⏳ 28 Tool catalog auto-generation (JSON schemas → markdown tables)

## Phase F — Communication Layer
- ⏳ 29 README hero rewrite pass 2 (after multi-model numbers land)
- ⏳ 30 Enterprise whitepaper / blog post (1500-2500 words, CISO/architect reader)
- ⏳ 31 Devpost final polish (media gallery, all form fields complete)
- ⏳ 32 Loom 5-min recording (multi-model toggle, accuracy curve, ablation moment)
- ⏳ 33 LinkedIn post + outreach plan (post Monday after submission)

## Phase G — Submission Mechanics
- ⏳ 34 Repo flip public — June 10 (MIT, signed tag, release notes)
- ⏳ 35 Final cross-checks — June 11-14 (cold-clone, make demo, all links, CI green)
- ⏳ 36 Submit Devpost — June 15

## Highest ROI remaining in order
3 ✅ → 4 → 8 → 23 → 16 → 19 → 32
