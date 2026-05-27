# SIFTGuard — Loom 5-min Recording Script

| Field | Value |
|---|---|
| Tag at script-lock | v1.40.1-task25-loom-script |
| Hard limit | 5:00 (SANS) |
| Target runtime | 4:30 (leaves 30s buffer for retakes / dead air trim) |
| Recording tool | Loom desktop, HD, webcam off, click highlights on |
| Capture region | 1920x1080, Do Not Disturb ON |

---

## Pre-flight — verify state, then record

**VM** — start dashboard if not running:
cd /cases/TEST-001/siftguard && source .venv/bin/activate && pgrep -af uvicorn || nohup .venv/bin/uvicorn siftguard.dashboard.app:app --host 0.0.0.0 --port 8080 --reload >> /tmp/uvicorn.log 2>&1 &
**VM** — pre-stage spoliation log (Beat 5 cats this on camera; never run live, suite takes 2 min):
cd /cases/TEST-001/siftguard && source .venv/bin/activate && pytest tests/spoliation/test_spoliation.py -v 2>&1 | grep -E "PASSED|FAILED|^=.*passed" > /tmp/spoliation_run.log && tail -3 /tmp/spoliation_run.log
Expected: last line shows `15 passed`.

**MAC** — get current VM IP (UTM reassigns it; do not assume 192.168.64.5):
arp -a | grep -i "sift|192.168.64" | head -5
**MAC** — SSH tunnel (replace IP with current):
ssh -f -N -L 8080:localhost:8080 sansforensics@192.168.64.6
**MAC** — verify dashboard loads + Panel 7 data flows:
curl -sf -o /dev/null -w "root: %{http_code}\n" http://localhost:8080/ && curl -s "http://localhost:8080/api/orchestrator-comparison/TEST-001?case=TEST-001" | python3 -c "import json,sys;d=json.load(sys.stdin)['rows'];[print(f'{k}: f1={v["mean_f1"]}') for k,v in d.items()]"
Expected: `root: 200`; all 5 orchestrators with non-null `mean_f1` on TEST-001. Open `http://localhost:8080` in Chrome and visually confirm Panel 7 shows 3 columns (TEST-001 / TEST-002 / TEST-003 ROCBA) with Native Loop row showing 0.867 cross-dataset mean.

**VM** — confirm tag:
cd /cases/TEST-001/siftguard && git tag -l | sort -V | tail -3
Expected: `v1.40.1-task25-loom-script` in the list.

---

## Recording environment (15% checklist)

- iTerm: 18pt JetBrains Mono, dark terminal background OK (dashboard stays GCP-light)
- Chrome zoom: 110% so Panel 7 F1 numbers are legible at 1080p
- Two windows pre-arranged: dashboard left (`http://localhost:8080`), terminal right
- Pre-stage commands in terminal scrollback (typed but not Entered): `siftguard run --case TEST-001` (Beat 1), `cat /tmp/spoliation_run.log` (Beat 5), `git tag -l | sort -V | tail -20` (Beat 8)
- Open file in VSCode behind: `docs/adr/ADR-006-multi-orchestrator-vendor-lockin.md` scrolled to §5.2
- Open file in second VSCode tab behind: `docs/LIMITATIONS.md` scrolled to §1
- One take target. Loom trim is fine for dead air; do not splice between beats.

---

## Beat-by-beat (timestamp · on-screen · voiceover)

### 0:00–0:20 — Hook (20s)

**Show:** Plain terminal, big font. `siftguard run --case TEST-001` already typed, cursor blinking. Don't press Enter yet.

**Voiceover:**
> "In November 2025, Anthropic disclosed GTG-1002 — a state-sponsored operation running autonomous reconnaissance and exploitation through Claude Code at 80 to 90 percent autonomy. Adversaries already move at machine speed. Defenders still look up command-line flags during active incidents. SIFTGuard closes that gap."

### 0:20–1:00 — Architecture (40s)

**Show:** Open `docs/architecture/architecture-v3.svg` full-screen in Chrome. Cursor traces: MCP server → 5 adapters → SnapshotWriter → audit DB.

**Voiceover:**
> "One typed MCP server wraps every SIFT tool — Volatility, FLS, RegRipper, timeline, MFT. Five orchestration paradigms call into it: Anthropic's native loop, LangGraph, OpenAI function calling, Gemini 3 Pro, and Claude Code headless. Same model API surface, same Pydantic-validated tools, same prompts across all five. Orchestration is the variable under test. Every action routes through an application-layer SnapshotWriter — no UPDATE or DELETE surface exists on the audit table. That's the integrity boundary."

### 1:00–2:00 — Live Native run on TEST-001 (60s)

**Show:** Cmd-Tab to dashboard. Click Native Loop. Cmd-Tab back to terminal. Press Enter on the pre-staged `siftguard run` command. Cmd-Tab to dashboard. IOC graph populates, audit trail streams, hypothesis panel updates.

**Voiceover:**
> "Live Native Loop run against TEST-001 — the SRL-2018 APT memory image, 5 gigabytes. The agent forms a hypothesis, sequences tools, updates its theory as findings come in. Watch the IOC graph populate — process tree shows lsass.exe handling, that's credential access. Network panel surfaces a connection to 23.194.110.27 — external exfiltration. The audit trail streams every tool call, every argument, every return — append-only by construction. Two iterations, three tools, eight IOCs, full incident report. F1 against ground truth: one-point-zero."

### 2:00–2:45 — Results mode, Panel 7 (45s)

**Show:** Click "Results" toggle in dashboard. Scroll to Panel 7. Cursor hovers Native Loop row.

**Voiceover:**
> "Switching to results mode. Panel 7 — orchestrator comparison across three datasets. TEST-001 memory APT, TEST-002 NTFS disk hacking case, TEST-003 ROCBA live IP-theft investigation. Native Loop is the only configuration that produces scoreable verdicts across all three. Cross-dataset mean F1: zero-point-eight-six-seven. Three orchestrators failed to surface disk artifacts at all — that failure mode is documented openly in LIMITATIONS.md. Same model API surface across all five adapters. Orchestration is what differs."

### 2:45–3:15 — Spoliation defense (30s)

**Show:** Cmd-Tab to terminal. Press Enter on the pre-staged `cat /tmp/spoliation_run.log`. The 15 PASSED lines + green `15 passed in 121.60s` summary fill the screen.

**Voiceover:**
> "Fifteen named attack scenarios — rm-rf, dd-of, mkfs, path traversal, shell redirects, chmod on evidence. Every one blocked at the function boundary by the application-layer safe-exec validator before any subprocess spawns. Not data-layer triggers — application-layer write discipline. The storage-hardening backlog is named explicitly in ADR-007 section 6."

### 3:15–3:45 — ADR-006 §5.2 (30s)

**Show:** Cmd-Tab to VSCode, `ADR-006-multi-orchestrator-vendor-lockin.md` at §5.2. Cursor highlights the 2.72× line.

**Voiceover:**
> "ADR-006, section 5.2. Cost-per-verdict spread across five orchestrators: two-point-seven-two times — cheapest to most expensive paradigm. Same model class, same tools, same prompts. What changed is orchestration. The decision to be vendor-and-framework-agnostic is operational and regulatory, not aesthetic. The ADR makes the case in prose."

### 3:45–4:05 — LIMITATIONS.md (20s)

**Show:** Cmd-Tab to second VSCode tab. `LIMITATIONS.md` open at §1. Scroll once.

**Voiceover:**
> "LIMITATIONS.md — what SIFTGuard cannot do today, when not to use it. Disk-evidence applicability gaps. OS-level isolation requirements for production deployment. Hardware-rooted attestation as future work. Engineering honesty is the signal."

### 4:05–4:30 — Close (25s)

**Show:** Cmd-Tab to terminal. Press Enter on pre-staged `git tag -l | sort -V | tail -20`. The tag list fills the screen.

**Voiceover:**
> "Final frame — the tag list. I tag every phase boundary so you can read the project as engineering archaeology. Forty release tags, each one a sealed decision. Repo is public at github.com/Nafsgerman/siftguard, MIT license. Find evil."

End on the tag list. No outro card.

---

## Post-record checklist (before uploading)

1. Watch playback once at 1× — confirm 0.867 is legible at 2:00, `15 passed` visible at 2:45, 2.72× legible at 3:15
2. Confirm IOC graph actually populated on screen during 1:00–2:00 beat
3. Confirm tag list is the final frame
4. Total runtime ≤ 5:00 — Devpost auto-rejects 5:01
5. Trim dead air with Loom edit; do not splice between beats

Upload Loom, copy public link, paste under "Final cut" heading below, then T26 (repo flip public).

---

## Final cut

_TBD — link goes here after recording._
