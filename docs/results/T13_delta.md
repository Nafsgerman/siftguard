# T13 — Protocol SIFT Baseline: Real F1 Scores (TEST-001)

**Case:** SRL-2018 APT Hunt (TEST-001)
**Ground Truth:** v1.1.0 — 4 applicable IOCs
**Scorer:** Report-text recall (tp/applicable_count)
**Date:** 2026-05-16

## Results

| Orchestrator        | Proxy F1 | Real F1 | Delta  | TP | FN |
|---------------------|----------|---------|--------|----|----|
| Native Loop (Sonnet)| 1.000    | 1.000   | +0.000 | 4  | 0  |
| LangGraph (Sonnet)  | —        | 0.750   | —      | 3  | 1  |
| OpenAI FC (gpt-5.5) | —        | 1.000   | —      | 4  | 0  |
| Gemini 2.5 Pro      | —        | 0.250   | —      | 1  | 3  |
| Claude Code         | —        | 1.000   | —      | 4  | 0  |

## Key findings

- Native Loop, OpenAI FC, Claude Code all achieve **F1=1.000** on TEST-001
- LangGraph misses `usbclient.exe` — 0.750
- Gemini 2.5 Pro misses 3/4 IOCs — result JSON lacks full report text; MD report not generated
- Single-variable discipline holds: orchestration is the only variable across all 5 runs
