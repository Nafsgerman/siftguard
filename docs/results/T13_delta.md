# T13 — Protocol SIFT Baseline: Paired-Dataset F1 (TEST-001 + TEST-002)

**Cases:** SRL-2018 APT Memory (TEST-001) + NIST CFReDS Hacking Case (TEST-002)
**Ground Truth:** v1.1.0 — 4 memory IOCs (TEST-001) + 8 disk IOCs (TEST-002)
**Scorer:** Report-text recall (TP / applicable_count)
**Date:** 2026-05-23

---

## Headline

Five orchestrators on two public datasets. Same prompts, same intended MCP tool catalog, same scoring methodology. The model-provider and orchestration stack is the variable.

| Orchestrator         | TEST-001 F1 | TEST-002 F1 | Mean  | Spread |
|----------------------|-------------|-------------|-------|--------|
| OpenAI FC (gpt-5.5)  | 1.000       | 0.750       | 0.875 | 0.250  |
| Native Loop (Sonnet) | 1.000       | 0.500       | 0.750 | 0.500  |
| Gemini 2.5 Pro       | 0.250       | 0.500       | 0.375 | 0.250  |
| LangGraph (Sonnet)   | 0.750       | 0.000       | 0.375 | 0.750  |
| Claude Code          | 1.000       | 0.000       | 0.500 | 1.000  |

---

## TEST-001 — Memory Surface (SRL-2018 APT, 4 IOCs)

| Orchestrator         | F1    | TP | FN |
|----------------------|-------|----|----|
| Native Loop (Sonnet) | 1.000 | 4  | 0  |
| OpenAI FC (gpt-5.5)  | 1.000 | 4  | 0  |
| Claude Code          | 1.000 | 4  | 0  |
| LangGraph (Sonnet)   | 0.750 | 3  | 1  |
| Gemini 2.5 Pro       | 0.250 | 1  | 3  |

**Misses.** LangGraph missed `usbclient.exe`. Gemini hallucinated wrong C2 IP (`192.168.1.107:4444` vs actual `172.16.4.10:8080`) and missed `ftusbsrvc.exe` + `usbclient.exe`.

## TEST-002 — Disk Surface (Schardt / Mr. Evil, 8 IOCs)

| Orchestrator         | F1    | TP | FN | Detail                                                            |
|----------------------|-------|----|----|-------------------------------------------------------------------|
| OpenAI FC (gpt-5.5)  | 0.750 | 6  | 2  | Missed Netcat (`file-005`), Schardt registered-owner (`user-002`) |
| Native Loop (Sonnet) | 0.500 | 4  | 4  | Missed Cain, pwdump, Netcat, WinPcap                              |
| Gemini 2.5 Pro       | 0.500 | 4  | 4  | Missed pwdump, Netcat, WinPcap, "Mr. Evil" profile                |
| LangGraph (Sonnet)   | 0.000 | 0  | 8  | Investigation incomplete — max_iterations after 15 iterations     |
| Claude Code          | 0.000 | 0  | 8  | Result null — adapter produced no report                          |

---

## Key findings

1. **OpenAI FC is the most consistent orchestrator across both surfaces** — 1.000 / 0.750. The only adapter that holds up when the evidence surface changes from memory to disk.

2. **Claude Code drops from 1.000 → 0.000.** Strongest single-case result on TEST-001, total failure on TEST-002. Subprocess CLI adapter is not robust to disk-image workloads in its current configuration.

3. **LangGraph drops from 0.750 → 0.000.** Hit max_iterations=15 without producing a report. Iteration budget tuned for memory hunts does not transfer to disk.

4. **Gemini is anti-correlated.** Worst on TEST-001 (0.250) but matches Sonnet baselines on TEST-002 (0.500). Different failure modes per surface.

5. **Native Sonnet is steady.** 1.000 → 0.500. No catastrophic failure; the model identifies high-signal IOCs (NetStumbler, Ethereal, the Mr. Evil profile) but misses lower-frequency tooling (Cain, pwdump, Netcat, WinPcap).

## Generalization claim

Memory-only results can mask orchestration fragility. Three of five orchestrators score 1.000 on TEST-001 and look indistinguishable. The same three orchestrators range 0.000 → 0.750 on TEST-002. **A single-dataset benchmark would have ranked Claude Code, OpenAI FC, and Native as equivalent. They are not.**

## Methodology

- Ground truth: `experiments/ground_truth/TEST-001-v1.1.0.json` + `experiments/ground_truth/TEST-002-v1.1.0.json`
- Scorer: `scripts/score_test002_v110.py` (TEST-002), existing scorer (TEST-001)
- Result source: most recent `result_*.json` per orchestrator under `experiments/results/baseline_*/TEST-002/`
- Recall = TP / applicable_count; precision not computed from text alone (documented limitation, field-level provenance in P2 backlog)

## ADR linkage

ADR-006 §5.2 cost-spread argument extends from cost to accuracy: spread across orchestration paradigms grows when the evidence surface changes. The single-dataset benchmark hides the variance the two-dataset benchmark exposes.
