# SIFTGuard — Loom 2-min demo script (T25)

Target: 120s exact. Loom record limit: 180s safety buffer.
Voiceover only. No talking-head bubble. 1080p. Cursor visible.
Read at ~140 WPM. Pause 0.5s between frames for cut clarity.

---

## Frame 1 — Problem (0:00 – 0:08)

**Visual:** Cold dashboard at `http://localhost:8080`, top of page, SIFTGuard wordmark + hero tagline visible.

**VO:**
> DFIR analysts spend hours triaging memory dumps. SIFTGuard does it
> autonomously — five orchestrators, one typed MCP server.

**On-screen callout:** none. Let the hero land.

---

## Frame 2 — Orchestrator toggle (0:08 – 0:30)

**Visual:** Click the orchestrator dropdown at top of dashboard. Hover
each option for ~1.5s in this order: Native Loop → LangGraph → OpenAI FC →
Gemini 3 Pro → Claude Code. Select Native Loop. Dashboard re-binds to that
adapter's cached run.

**VO:**
> Watch the toggle. Native loop. LangGraph. OpenAI function-calling on
> GPT-5.5. Gemini 3 Pro. Claude Code headless. Same evidence file, same
> typed tools — only the orchestration paradigm changes. That is the
> experimental contract.

**On-screen callout (overlay text, bottom-left):**
> 5 orchestrators · 1 typed MCP server · identical evidence

---

## Frame 3 — Panel 7 F1 + cost spread (0:30 – 0:58)

**Visual:** Scroll to Panel 7. Cursor traces the F1 column top-to-bottom
(linger on the three 1.000 rows). Then trace the Cost column (linger on
$0.1949 → $0.5293 endpoints).

**VO:**
> Panel 7. Three of five orchestrators hit F1 equals one-point-zero on
> SRL-2018. Baseline variance: sigma equals zero across six seeds.
> Reproducibility is settled. But cost-per-verdict spreads
> two-point-seven-two-X on the same evidence — OpenAI function-calling at
> nineteen cents, Claude Code headless at fifty-three. That gap is not
> noise. It is paradigm. ADR-006 documents the call.

**On-screen callout (overlay text, top-right):**
> 2.72× cost spread · σ = 0.000 · ADR-006 §5.2

---

## Frame 4 — Spoliation: architectural not prompt (0:58 – 1:20)

**Visual:** Cut to terminal (iTerm, dark theme is fine here for contrast).
Run: `python -m pytest tests/spoliation/test_spoliation.py -v`.
Camera lingers on the 12 `PASSED` lines and the final summary
`12 passed in 0.02s`.

**VO:**
> Evidence integrity is not a prompt instruction. The agent literally
> cannot call rm, dd, or mkfs — they are absent from the MCP allowlist.
> Twelve spoliation scenarios, twelve blocked at the function boundary,
> in twenty milliseconds. The system prompt is defense-in-depth. The
> architecture is the wall.

**On-screen callout (overlay text, bottom):**
> 12/12 architectural · not 12/12 prompt-instructed

---

## Frame 5 — Engineering archaeology (1:20 – 1:42)

**Visual:** Cut to terminal. Run: `git tag --list 'v*' --sort=-v:refname | head -12`.
The tag list scrolls: `v1.29.0-task24-devpost`, `v1.28.0-task23-readme-hero`,
`v1.16.0-task10-adr006`, `v1.16.0-task9-complete`, `v1.9.0-phase-a-complete`,
and back. Linger 4s.

**VO:**
> Every architectural decision is an ADR. Every phase boundary is a git
> tag. I tag every phase boundary so you can read the project as
> engineering archaeology. The repository is its own paper trail —
> reviewers can walk it backwards.

**On-screen callout (overlay text, bottom-right):**
> 30+ tags · 7 ADRs · public June 10

---

## Frame 6 — Close (1:42 – 2:00)

**Visual:** Cut back to dashboard hero. Hold the SIFTGuard wordmark
center-frame for 4s, then fade.

**VO:**
> Two public datasets. Five orchestrators. One typed tool surface. Zero
> hallucinated findings — every claim traces to an audit DB row.
> SIFTGuard: audit-first autonomous DFIR benchmark — rigorous, measurable, and transparent about its boundaries.

**On-screen callout:** none. The wordmark closes.

---

## Dashboard click path (exact sequence)

1. Frame 1: open `http://localhost:8080`, scroll position 0
2. Frame 2: click `#orchestrator-select` dropdown, hover each `<option>` in id order:
   `siftguard-v2 → siftguard-langgraph → siftguard-openai-fc → siftguard-gemini → siftguard-claudecode`,
   select `siftguard-v2`
3. Frame 3: scroll to `#panel-7`, cursor F1 column then cost column
4. Frame 4: ⌘-tab to iTerm
5. Frame 5: iTerm second tab with git tag command pre-typed
6. Frame 6: ⌘-tab back to browser, scroll to top

## Loom record config

- Resolution: 1080p
- Camera: OFF
- Mic: ON, noise-suppression enabled
- Annotation: OFF (overlays are pre-baked in script callouts above; add in
  Loom's post-record editor only if Loom is the final host, otherwise burn
  in via Descript / iMovie)
- Hard ceiling: 130s upload — anything over re-record

## Post-record

1. Loom → Share → copy public URL (visibility: anyone with link)
2. Paste URL into `docs/devpost/SUBMISSION.md` "Video demo link" field
3. Paste same URL into Devpost form "Video Demo Link"
4. Paste URL into Devpost "Media Gallery" as an embed
