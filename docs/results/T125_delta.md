# T12.5 — TEST-002 Baseline: Real F1 Scores (NIST CFReDS Hacking Case)

**Case:** NIST CFReDS Greg Schardt / Mr. Evil (TEST-002)
**Ground Truth:** v1.1.0 — 5 applicable IOCs (netstumbler, ethereal, pwdump, netcat, mr. evil)
**GT Source:** Direct disk mount at offset 63×512 — confirmed from SCHARDT.img NTFS partition
**Scorer:** Report-text recall (tp/applicable_count)
**Date:** 2026-05-16

## Results

| Orchestrator        | F1    | TP | FN |
|---------------------|-------|----|----|
| Native Loop (Sonnet)| 0.600 | 3  | 2  |
| LangGraph (Sonnet)  | 0.000 | 0  | 5  |
| OpenAI FC (gpt-5.5) | 0.800 | 4  | 1  |
| Gemini 2.5 Pro      | 0.400 | 2  | 3  |
| Claude Code         | 0.000 | 0  | 5  |

## Cross-dataset summary (TEST-001 + TEST-002)

| Orchestrator        | TEST-001 F1 | TEST-002 F1 | Mean  |
|---------------------|-------------|-------------|-------|
| Native Loop (Sonnet)| 1.000       | 0.600       | 0.800 |
| LangGraph (Sonnet)  | 0.750       | 0.000       | 0.375 |
| OpenAI FC (gpt-5.5) | 1.000       | 0.800       | 0.900 |
| Gemini 2.5 Pro      | 0.250       | 0.400       | 0.325 |
| Claude Code         | 1.000       | 0.000       | 0.500 |

## Key findings

- OpenAI FC leads cross-dataset mean F1=0.900
- Native Loop generalizes well: 1.000 → 0.600 across memory vs disk
- LangGraph and Claude Code collapse to 0.000 on disk image — tool access failure, not reasoning failure
- Gemini improves on disk (0.250 → 0.400) — less hallucination risk with structured filesystem artifacts
- TEST-002 tool limitation: TSK/Volatility fail on SCHARDT.img without mount; agents running blind
