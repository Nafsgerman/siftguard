# API Cost Ledger — SIFTGuard

Total spend on LLM APIs across all SIFTGuard development: **~$35 USD**.

This ledger exists because frontier-lab AI engineering is partly about cost
discipline. Every paid call documented; every category of spend rationalized.

## Spend by phase

| Phase | Window | Approx spend | What it bought |
|---|---|---|---|
| Phase A — Initial agent loop | May 1–6 | ~$6 | First end-to-end agent runs against TEST-001, found APT in SRL-2018 dataset, validated MCP server design |
| Phase B — Eval matrix | May 7–9 | ~$15 | 8-config ablation matrix: iter_sweep_{1,3,5,10}, baseline, v1, no_self_correction, no_correlation — produced Panels 4 (Pareto), 5 (hypothesis evolution), 6 (ablation) |
| Phase C — Multi-orchestrator | May 10–14 | ~$8 | 5 orchestrators × TEST-001 baseline: Native, LangGraph, OpenAI FC, Gemini 2.5 Pro, Claude Code headless. Produced ADR-006 cost-spread evidence ($0.1949 → $0.5293, 2.72× spread, σ=0.000) |
| Phase C lite — Generalization | May 15–17 | ~$5 | 5 orchestrators × TEST-002 NIST CFReDS Hacking Case. Cross-dataset F1 leaderboard: OpenAI FC 0.900, Native 0.800. T12.5 SCHARDT.img mount investigation. |
| Phase F — Demo dry-run | May 20 | ~$0.25 | Live agent run for Loom recording validation. Produced run_id `50665b3e-6506-4a3a-90e5-213f24b4e58d`, 10 auditentry rows, real self-correction sequence. |
| **Total** | | **~$34.25** | |

## Spend per orchestrator (TEST-001, single run, Sonnet 4.5 / GPT-5.5 / Gemini 2.5 Pro)

| Orchestrator | Model | Cost | Iterations | Wall time | Tokens (in/out) |
|---|---|---|---|---|---|
| siftguard-v2 (Native) | claude-sonnet-4-6 | $0.2308 | 7 | 104.0 s | — |
| siftguard-langgraph | claude-sonnet-4-6 | $0.2289 | 7 | 106.2 s | — |
| siftguard-openai-fc | gpt-5.5 | $0.1949 | 4 | 132.2 s | — |
| siftguard-gemini | gemini-2.5-pro | $0.2591 | 5 | 146.7 s | — |
| siftguard-claudecode | claude-sonnet-4-6 (headless) | $0.5293 | 18 | 258.7 s | — |

Cost spread: **2.72×** (OpenAI FC → Claude Code) on identical evidence file with
σ = 0.000 on baseline. Structural, not noise (ADR-006 §5.2).

## What we deliberately did NOT spend money on

- Re-validation runs for documentation-only changes (post May 16, after enforcing
  the "no paid API calls just to verify a doc edit" rule)
- Multiple seeds beyond n=6 for baseline (diminishing returns, σ already = 0)
- Re-running cached orchestrators when the audit DB already had the artifacts
- Cross-orchestrator runs on TEST-002 for orchestrators that fail on raw disk
  (LangGraph, Claude Code — tool-applicability failure, no reasoning signal)

## Operating discipline

After May 16, every paid API call was preceded by an explicit cost estimate
in chat and required confirmation before triggering. Memory rule:
*"NEVER trigger fresh agent runs just to validate code changes. Always check
first if existing audit DB rows / result files can validate the change."*

## G2 — Self-Correction Ablation Verification Runs (2026-05-22)

| Run | Orchestrator | self_correction | Elapsed | Iterations | Tool Calls | Retries | Path Fixes | Cost (est.) |
|-----|-------------|-----------------|---------|------------|------------|---------|------------|-------------|
| OFF | LangGraph   | False           | 2:41    | 5          | 10         | 4       | 4          | ~$0.20      |
| ON  | LangGraph   | True            | 5:08    | 5          | 10         | 5       | 3          | ~$0.25      |

**Ablation diff confirmed:** OFF run proceeds to verdict on MFT failure without substitution.
ON run attempts `create_supertimeline` substitution after MFT failure (+2:27, +1 retry).
Gate string: `SELF-CORRECTION DISABLED` prefix in `src/siftguard/agent/system_prompt_gate.py`.

## G2 — Self-Correction Ablation Verification Runs (2026-05-22)

| Run | Orchestrator | self_correction | Elapsed | Iterations | Tool Calls | Retries | Path Fixes | Cost (est.) |
|-----|-------------|-----------------|---------|------------|------------|---------|------------|-------------|
| OFF | LangGraph   | False           | 2:41    | 5          | 10         | 4       | 4          | ~$0.20      |
| ON  | LangGraph   | True            | 5:08    | 5          | 10         | 5       | 3          | ~$0.25      |

**Ablation diff confirmed:** OFF run proceeds to verdict on MFT failure without substitution.
ON run attempts `create_supertimeline` substitution after MFT failure (+2:27, +1 retry).
Gate string: `SELF-CORRECTION DISABLED` prefix in `src/siftguard/agent/system_prompt_gate.py`.
