# T14 v2 → Sonnet Handoff (updated with Mode Toggle)

**Tag:** v1.19.2-task14-v2-merged-modes · **Date:** May 17 2026
**Carry to T15:** Backend wiring, ADR-007 scorer, ADR-006 §generalization

## Two modes — Results vs Run Live

Top-right header toggle: `[ Results ] [ Run Live ]`

**Results mode** (default on page load) — clean evaluation view for judges:
- Hidden: case pill, timer, status pill, metrics strip, New Investigation form, Live Run nav item
- Visible: 9 result panels (Accuracy / Models / Spoliation / IOC Graph / Datasets / Orch Config / Evidence Chain / Eval / Limitations)
- Default active panel: 01 Accuracy

**Run Live mode** (one click to enter) — full live-investigation chrome:
- All Results-mode panels still visible
- Plus: case pill + timer + status pill in header
- Plus: metrics strip (Iterations / Tools / Findings / IOCs / Avg Time)
- Plus: New Investigation form in sidebar
- Plus: Live Run panel (P00) appears at top of nav
- Default active panel: 00 Live Run

Switching is purely UI — investigation state persists across mode flips. Judge can browse results while their run streams in background.

## Launch flow

Already wired:
- POST `/api/investigate` with `{case_id, image_path, briefing, orchestrator}`
- On 200 → marked `// TODO Sonnet` for stream subscription
- On failure → **mock streaming** kicks in (19 realistic forensic events, metrics tick, taxonomy populates, status flips green at end)

Demo works with or without backend.

## What Sonnet does tomorrow

**1. Confirm backend contract:**

VM:
```bash
grep -n "@app\|async def\|def " /cases/TEST-001/siftguard/src/app.py | head -60
```

**2. Replace the TODO in `launchInvestigation()`** — line marked `// TODO Sonnet: subscribe to /api/stream EventSource or poll /api/state`. Use SSE if backend supports it, else poll.

**3. Map backend event types to frontend tags:**
- tool call → `pushTrail('tool', msg)` + `state.tools++` + push duration to `state.toolTimes`
- finding → `pushTrail('find', msg)` + `state.find++`
- IOC → `pushTrail('ioc', msg)` + `state.ioc++`
- self-correction → `pushTrail('sys', msg)` + bump `state.tax.{retry|path|hall|conf}`
- iteration boundary → `state.iter++`
- complete → call existing complete block (stop timer, flip status green, re-enable button)

## Deployment

Mac:
```bash
scp /Users/nafees/Desktop/Nafees/Hackathon/siftguard/index.html sansforensics@192.168.64.5:/cases/TEST-001/siftguard/index.html
```

VM:
```bash
cd /cases/TEST-001/siftguard && python3 -m http.server 8080
```

## Git

Mac:
```bash
cd /Users/nafees/Desktop/Nafees/Hackathon/siftguard && git add index.html && git commit -m "T14 v2: dashboard with Results/Run Live mode toggle, IOC graph, spoliation, live trail" && git push
```

## Demo run order

1. Land on Results mode — clean, just F1 scores · Panel 01 active
2. Click around panels 7, 8, 9 — model ranking, spoliation moat, IOC graph
3. Click top-right "Run Live" toggle — full investigation chrome appears
4. Configure case in left form
5. Click Launch → mock stream fires, metrics tick up
6. Toggle back to Results while running — clean again, run continues in background
7. Switch back to Run Live to see completion

The toggle solves the "is this live or pre-baked?" confusion. Default is unambiguous: Results.
