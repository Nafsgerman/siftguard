#!/usr/bin/env python3
"""T14: Accordion shell + data corrections for src/siftguard/dashboard/index.html

Run from repo root:
    python scripts/apply_t14.py

Changes:
  - Accordion CSS added
  - P1+P7 expanded by default; P2-P6 collapsed accordion sections below
  - Sidebar nav: P1/P7/P2-P6 removed (now in accordion); P0/P8/P9 kept
  - P7 numbers corrected to T13 real data (0.875 leader, 0.750 runner-up)
  - P1 TEST-002 numbers corrected (0.750/0.500/0.500)
  - P8 "append-only" language stripped from dashboard header
  - Version tag updated to v1.17.3-task14
"""

import re
import sys
from pathlib import Path

INDEX = Path("src/siftguard/dashboard/index.html")
if not INDEX.exists():
    print(f"ERROR: {INDEX} not found. Run from repo root.", file=sys.stderr)
    sys.exit(1)

html = INDEX.read_text()
original_len = len(html)


def replace_once(content, old, new, label):
    if old not in content:
        print(f"  WARN [{label}]: anchor not found — skipping")
        return content
    result = content.replace(old, new, 1)
    print(f"  OK   [{label}]")
    return result


# ── 1. CSS: accordion styles ──────────────────────────────────────────────────
ACC_CSS = """
/* Accordion layout (T14) */
.accordion-wrap{padding:20px}
.acc-panel{background:var(--white);border:1px solid var(--gray-200);border-radius:var(--rl);margin-bottom:10px;box-shadow:var(--shadow-sm);overflow:hidden}
.acc-header{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;cursor:pointer;user-select:none;transition:background .12s;gap:12px}
.acc-header:hover{background:var(--gray-50)}
.acc-header.open{border-bottom:1px solid var(--gray-200)}
.acc-header.acc-hero{border-left:3px solid var(--blue);background:var(--blue-light)}
.acc-header.acc-hero:hover{background:#dceafe}
.acc-hdr-text{flex:1;min-width:0}
.acc-title{font-family:var(--display);font-size:15px;font-weight:700;color:var(--gray-900);letter-spacing:-.2px;display:flex;align-items:center;gap:8px}
.acc-num{font-family:var(--mono);font-size:10px;color:var(--gray-400);font-weight:400;background:var(--gray-100);padding:2px 6px;border-radius:4px}
.acc-hero .acc-title{color:var(--blue)}
.acc-hero .acc-num{background:rgba(26,115,232,.12);color:var(--blue)}
.acc-sub{font-size:11px;color:var(--gray-600);margin-top:2px}
.acc-chevron{width:18px;height:18px;fill:none;stroke:var(--gray-600);stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex-shrink:0;transition:transform .2s}
.acc-chevron.open{transform:rotate(180deg)}
.acc-body{padding:16px 18px 18px}
"""
html = replace_once(html, "/* Live Run panel */", ACC_CSS + "/* Live Run panel */", "accordion CSS")

# ── 2. Version tag ────────────────────────────────────────────────────────────
html = replace_once(html, "v1.19.1-task125", "v1.17.3-task14", "version tag")

# ── 3. Sidebar: update stale P7 badge ────────────────────────────────────────
html = replace_once(
    html,
    '<span class="nav-badge nb-blue">0.900</span>',
    '<span class="nav-badge nb-blue">0.875</span>',
    "p7 badge",
)

# ── 4. Sidebar: remove P1 nav item ───────────────────────────────────────────
p1_pattern = r'    <div class="nav-item active" data-panel="p1"[^>]*>.*?</div>'
m = re.search(p1_pattern, html, re.DOTALL)
if m:
    html = html[: m.start()] + html[m.end() :]
    print("  OK   [remove p1 nav]")
else:
    print("  WARN [remove p1 nav]: not found")

# ── 5. Sidebar: remove P7 nav item ───────────────────────────────────────────
p7_pattern = r'    <div class="nav-item" data-panel="p7"[^>]*>.*?</div>'
m = re.search(p7_pattern, html, re.DOTALL)
if m:
    html = html[: m.start()] + html[m.end() :]
    print("  OK   [remove p7 nav]")
else:
    print("  WARN [remove p7 nav]: not found")

# ── 6. Sidebar: remove P2-P6 nav items ───────────────────────────────────────
for panel in ["p2", "p3", "p4", "p5", "p6"]:
    pattern = rf'    <div class="nav-item" data-panel="{panel}"[^>]*>.*?</div>'
    m = re.search(pattern, html, re.DOTALL)
    if m:
        html = html[: m.start()] + html[m.end() :]
        print(f"  OK   [remove {panel} nav]")
    else:
        print(f"  WARN [remove {panel} nav]: not found")

# ── 7. Sidebar: add Results label before P8 ──────────────────────────────────
html = replace_once(
    html,
    '    <div class="nav-item" data-panel="p8"',
    '    <div class="sb-sec" style="margin-top:4px"><svg viewBox="0 0 24 24" style="width:11px;height:11px;fill:var(--gray-600)"><path d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>Detailed Panels</div>\n    <div class="nav-item" data-panel="p8"',
    "results label",
)

# ── 8. Replace P1+P7 panels + P2-P6 panels with accordion ────────────────────
OLD_PANELS = """    <!-- P1: Accuracy -->
    <div class="panel active" id="p1">
      <div class="panel-hdr"><h1>Accuracy — Real F1 Scores</h1><p>Per-orchestrator detection accuracy across both test datasets · T13 + T12.5 verified</p></div>
      <div class="card">
        <div class="case-tabs">
          <button class="case-tab active" onclick="switchCase('001',this)">TEST-001</button>
          <button class="case-tab" onclick="switchCase('002',this)">TEST-002 (NIST CFReDS)</button>
        </div>
        <div id="case-001">
          <div class="f1-grid">
            <div class="f1-card perfect"><div class="f1-orch">Native Claude</div><div class="f1-score perfect">1.000</div><div class="f1-bar"><div class="f1-bar-fill" style="width:100%;background:var(--green)"></div></div></div>
            <div class="f1-card perfect"><div class="f1-orch">OpenAI FC</div><div class="f1-score perfect">1.000</div><div class="f1-bar"><div class="f1-bar-fill" style="width:100%;background:var(--green)"></div></div></div>
            <div class="f1-card perfect"><div class="f1-orch">ClaudeCode</div><div class="f1-score perfect">1.000</div><div class="f1-bar"><div class="f1-bar-fill" style="width:100%;background:var(--green)"></div></div></div>
            <div class="f1-card mid"><div class="f1-orch">LangGraph</div><div class="f1-score mid">0.750</div><div class="f1-bar"><div class="f1-bar-fill" style="width:75%;background:var(--amber)"></div></div></div>
            <div class="f1-card low"><div class="f1-orch">Gemini</div><div class="f1-score low">0.250</div><div class="f1-bar"><div class="f1-bar-fill" style="width:25%;background:var(--red)"></div></div></div>
          </div>
          <div class="note-warn">Gemini 0.250 confirmed genuine hallucination — not tool failure. LangGraph 0.750 is reasoning gap, not environment gap.</div>
        </div>
        <div id="case-002" style="display:none">
          <div class="gaps"><strong>Known gaps — carry to T15</strong><ul><li>LangGraph + ClaudeCode 0.000 = tool access failure on raw disk image — ADR-006</li><li>Scorer running in report-text fallback mode — ADR-009</li></ul></div>
          <div class="f1-grid">
            <div class="f1-card good"><div class="f1-orch">OpenAI FC</div><div class="f1-score good">0.800</div><div class="f1-bar"><div class="f1-bar-fill" style="width:80%;background:var(--blue)"></div></div></div>
            <div class="f1-card mid"><div class="f1-orch">Native Claude</div><div class="f1-score mid">0.600</div><div class="f1-bar"><div class="f1-bar-fill" style="width:60%;background:var(--amber)"></div></div></div>
            <div class="f1-card low"><div class="f1-orch">Gemini</div><div class="f1-score low">0.400</div><div class="f1-bar"><div class="f1-bar-fill" style="width:40%;background:var(--red)"></div></div></div>
            <div class="f1-card zero"><div class="f1-orch">LangGraph</div><div class="f1-score zero">0.000</div><div class="f1-bar"><div class="f1-bar-fill" style="width:0%"></div></div></div>
            <div class="f1-card zero"><div class="f1-orch">ClaudeCode</div><div class="f1-score zero">0.000</div><div class="f1-bar"><div class="f1-bar-fill" style="width:0%"></div></div></div>
          </div>
        </div>
      </div>
    </div>

    <!-- P7: Models -->
    <div class="panel" id="p7">
      <div class="panel-hdr"><h1>Model Comparison — Cross-Dataset Mean F1</h1><p>Ranking across TEST-001 + TEST-002 NIST CFReDS · 5 orchestrators · 10 runs total</p></div>
      <div class="card">
        <div class="mean-row">
          <div class="mean-hero-card"><div class="mean-hero-lbl">Cross-dataset leader</div><div class="mean-hero-val">0.900</div><div class="mean-hero-sub">OpenAI Function Calling</div></div>
          <div class="mean-runner"><div style="font-size:10px;color:var(--gray-600);font-weight:500;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Runner-up</div><div style="font-family:var(--display);font-size:28px;font-weight:700;color:var(--gray-900);letter-spacing:-1px;line-height:1">0.800</div><div style="font-size:12px;color:var(--gray-600);margin-top:3px;font-weight:500">Native Claude</div></div>
        </div>
        <table class="rank-table">
          <thead><tr><th>#</th><th>Orchestrator</th><th>TEST-001</th><th>TEST-002</th><th>Bar</th><th style="text-align:right">Mean</th><th style="text-align:right;color:var(--blue)">↺ Corrections</th></tr></thead>
          <tbody>
            <tr id="p7r-siftguard-openai-fc"><td style="font-family:var(--mono);font-size:10px;color:var(--gray-400)">1</td><td style="font-weight:500">OpenAI FC</td><td><span style="color:var(--green);font-family:var(--mono);font-size:12px;font-weight:500">1.000</span></td><td><span style="color:var(--blue);font-family:var(--mono);font-size:12px;font-weight:500">0.800</span></td><td><div class="rbar-bg"><div class="rbar-fill" style="width:90%"></div></div></td><td class="rscore" style="color:var(--blue)">0.900</td><td class="rscore" id="p7c-siftguard-openai-fc" style="color:var(--gray-400)">—</td></tr>
            <tr id="p7r-siftguard-v2"><td style="font-family:var(--mono);font-size:10px;color:var(--gray-400)">2</td><td style="font-weight:500">Native Claude</td><td><span style="color:var(--green);font-family:var(--mono);font-size:12px;font-weight:500">1.000</span></td><td><span style="color:#b06000;font-family:var(--mono);font-size:12px;font-weight:500">0.600</span></td><td><div class="rbar-bg"><div class="rbar-fill" style="width:80%"></div></div></td><td class="rscore">0.800</td><td class="rscore" id="p7c-siftguard-v2" style="color:var(--gray-400)">—</td></tr>
            <tr id="p7r-siftguard-claudecode"><td style="font-family:var(--mono);font-size:10px;color:var(--gray-400)">3</td><td style="font-weight:500">ClaudeCode</td><td><span style="color:var(--green);font-family:var(--mono);font-size:12px;font-weight:500">1.000</span></td><td><span style="color:var(--gray-400);font-family:var(--mono);font-size:12px;font-weight:500">0.000</span></td><td><div class="rbar-bg"><div class="rbar-fill" style="width:50%"></div></div></td><td class="rscore">0.500</td><td class="rscore" id="p7c-siftguard-claudecode" style="color:var(--gray-400)">—</td></tr>
            <tr id="p7r-siftguard-langgraph"><td style="font-family:var(--mono);font-size:10px;color:var(--gray-400)">4</td><td style="font-weight:500">LangGraph</td><td><span style="color:#b06000;font-family:var(--mono);font-size:12px;font-weight:500">0.750</span></td><td><span style="color:var(--gray-400);font-family:var(--mono);font-size:12px;font-weight:500">0.000</span></td><td><div class="rbar-bg"><div class="rbar-fill" style="width:37.5%"></div></div></td><td class="rscore">0.375</td><td class="rscore" id="p7c-siftguard-langgraph" style="color:var(--gray-400)">—</td></tr>
            <tr id="p7r-siftguard-gemini"><td style="font-family:var(--mono);font-size:10px;color:var(--gray-400)">5</td><td style="font-weight:500">Gemini</td><td><span style="color:var(--red);font-family:var(--mono);font-size:12px;font-weight:500">0.250</span></td><td><span style="color:var(--red);font-family:var(--mono);font-size:12px;font-weight:500">0.400</span></td><td><div class="rbar-bg"><div class="rbar-fill" style="width:32.5%"></div></div></td><td class="rscore" style="color:var(--red)">0.325</td><td class="rscore" id="p7c-siftguard-gemini" style="color:var(--gray-400)">—</td></tr>
          </tbody>
        </table>
        <div class="note-warn">ClaudeCode + LangGraph 0.000 on TEST-002 = tool access failure on raw disk image, not reasoning failure. ADR-006 §generalization.</div>
      </div>
    </div>

    <!-- P8: Spoliation -->"""

NEW_PANELS = """    <!-- Accordion: P1+P7 hero (open), P2-P6 collapsed (T14) -->
    <div id="results-accordion" class="accordion-wrap">

      <!-- P1: Accuracy — hero, open by default -->
      <div class="acc-panel">
        <div class="acc-header acc-hero open" onclick="toggleAcc('acc-p1',this)">
          <div class="acc-hdr-text">
            <div class="acc-title"><span class="acc-num">01</span>Accuracy — Real F1 Scores</div>
            <div class="acc-sub">Per-orchestrator detection accuracy · 2 datasets · T13 verified</div>
          </div>
          <svg class="acc-chevron open" viewBox="0 0 24 24"><path d="M19 9l-7 7-7-7"/></svg>
        </div>
        <div class="acc-body" id="acc-p1">
          <div class="card">
            <div class="case-tabs">
              <button class="case-tab active" onclick="switchCase('001',this)">TEST-001</button>
              <button class="case-tab" onclick="switchCase('002',this)">TEST-002 (NIST CFReDS)</button>
            </div>
            <div id="case-001">
              <div class="f1-grid">
                <div class="f1-card perfect"><div class="f1-orch">Native Claude</div><div class="f1-score perfect">1.000</div><div class="f1-bar"><div class="f1-bar-fill" style="width:100%;background:var(--green)"></div></div></div>
                <div class="f1-card perfect"><div class="f1-orch">OpenAI FC</div><div class="f1-score perfect">1.000</div><div class="f1-bar"><div class="f1-bar-fill" style="width:100%;background:var(--green)"></div></div></div>
                <div class="f1-card perfect"><div class="f1-orch">ClaudeCode</div><div class="f1-score perfect">1.000</div><div class="f1-bar"><div class="f1-bar-fill" style="width:100%;background:var(--green)"></div></div></div>
                <div class="f1-card mid"><div class="f1-orch">LangGraph</div><div class="f1-score mid">0.750</div><div class="f1-bar"><div class="f1-bar-fill" style="width:75%;background:var(--amber)"></div></div></div>
                <div class="f1-card low"><div class="f1-orch">Gemini</div><div class="f1-score low">0.250</div><div class="f1-bar"><div class="f1-bar-fill" style="width:25%;background:var(--red)"></div></div></div>
              </div>
              <div class="note-warn">Gemini 0.250 confirmed genuine hallucination — not tool failure. LangGraph 0.750 is reasoning gap, not environment gap.</div>
            </div>
            <div id="case-002" style="display:none">
              <div class="gaps"><strong>Known gaps — carry to T15</strong><ul><li>LangGraph + ClaudeCode 0.000 = tool access failure on raw disk image — ADR-006</li><li>Scorer running in report-text fallback mode — ADR-009</li></ul></div>
              <div class="f1-grid">
                <div class="f1-card good"><div class="f1-orch">OpenAI FC</div><div class="f1-score good">0.750</div><div class="f1-bar"><div class="f1-bar-fill" style="width:75%;background:var(--blue)"></div></div></div>
                <div class="f1-card mid"><div class="f1-orch">Native Claude</div><div class="f1-score mid">0.500</div><div class="f1-bar"><div class="f1-bar-fill" style="width:50%;background:var(--amber)"></div></div></div>
                <div class="f1-card mid"><div class="f1-orch">Gemini</div><div class="f1-score mid">0.500</div><div class="f1-bar"><div class="f1-bar-fill" style="width:50%;background:var(--amber)"></div></div></div>
                <div class="f1-card zero"><div class="f1-orch">LangGraph</div><div class="f1-score zero">0.000</div><div class="f1-bar"><div class="f1-bar-fill" style="width:0%"></div></div></div>
                <div class="f1-card zero"><div class="f1-orch">ClaudeCode</div><div class="f1-score zero">0.000</div><div class="f1-bar"><div class="f1-bar-fill" style="width:0%"></div></div></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- P7: Model Comparison — hero, open; T13 real numbers -->
      <div class="acc-panel">
        <div class="acc-header acc-hero open" onclick="toggleAcc('acc-p7',this)">
          <div class="acc-hdr-text">
            <div class="acc-title"><span class="acc-num">07</span>Model Comparison — Cross-Dataset Mean F1</div>
            <div class="acc-sub">Ranking across TEST-001 + TEST-002 · 5 orchestrators · spread 0.000–0.875</div>
          </div>
          <svg class="acc-chevron open" viewBox="0 0 24 24"><path d="M19 9l-7 7-7-7"/></svg>
        </div>
        <div class="acc-body" id="acc-p7">
          <div class="card">
            <div class="mean-row">
              <div class="mean-hero-card"><div class="mean-hero-lbl">Cross-dataset leader</div><div class="mean-hero-val">0.875</div><div class="mean-hero-sub">OpenAI Function Calling</div></div>
              <div class="mean-runner"><div style="font-size:10px;color:var(--gray-600);font-weight:500;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Runner-up</div><div style="font-family:var(--display);font-size:28px;font-weight:700;color:var(--gray-900);letter-spacing:-1px;line-height:1">0.750</div><div style="font-size:12px;color:var(--gray-600);margin-top:3px;font-weight:500">Native Claude</div></div>
            </div>
            <table class="rank-table">
              <thead><tr><th>#</th><th>Orchestrator</th><th>TEST-001</th><th>TEST-002</th><th>Bar</th><th style="text-align:right">Mean</th><th style="text-align:right;color:var(--blue)">&#8635; Corrections</th></tr></thead>
              <tbody>
                <tr id="p7r-siftguard-openai-fc"><td style="font-family:var(--mono);font-size:10px;color:var(--gray-400)">1</td><td style="font-weight:500">OpenAI FC</td><td><span style="color:var(--green);font-family:var(--mono);font-size:12px;font-weight:500">1.000</span></td><td><span style="color:var(--blue);font-family:var(--mono);font-size:12px;font-weight:500">0.750</span></td><td><div class="rbar-bg"><div class="rbar-fill" style="width:87.5%"></div></div></td><td class="rscore" style="color:var(--blue)">0.875</td><td class="rscore" id="p7c-siftguard-openai-fc" style="color:var(--gray-400)">—</td></tr>
                <tr id="p7r-siftguard-v2"><td style="font-family:var(--mono);font-size:10px;color:var(--gray-400)">2</td><td style="font-weight:500">Native Claude</td><td><span style="color:var(--green);font-family:var(--mono);font-size:12px;font-weight:500">1.000</span></td><td><span style="color:#b06000;font-family:var(--mono);font-size:12px;font-weight:500">0.500</span></td><td><div class="rbar-bg"><div class="rbar-fill" style="width:75%"></div></div></td><td class="rscore">0.750</td><td class="rscore" id="p7c-siftguard-v2" style="color:var(--gray-400)">—</td></tr>
                <tr id="p7r-siftguard-claudecode"><td style="font-family:var(--mono);font-size:10px;color:var(--gray-400)">3</td><td style="font-weight:500">ClaudeCode</td><td><span style="color:var(--green);font-family:var(--mono);font-size:12px;font-weight:500">1.000</span></td><td><span style="color:var(--gray-400);font-family:var(--mono);font-size:12px;font-weight:500">0.000</span></td><td><div class="rbar-bg"><div class="rbar-fill" style="width:50%"></div></div></td><td class="rscore">0.500</td><td class="rscore" id="p7c-siftguard-claudecode" style="color:var(--gray-400)">—</td></tr>
                <tr id="p7r-siftguard-langgraph"><td style="font-family:var(--mono);font-size:10px;color:var(--gray-400)">4</td><td style="font-weight:500">LangGraph</td><td><span style="color:#b06000;font-family:var(--mono);font-size:12px;font-weight:500">0.750</span></td><td><span style="color:var(--gray-400);font-family:var(--mono);font-size:12px;font-weight:500">0.000</span></td><td><div class="rbar-bg"><div class="rbar-fill" style="width:37.5%"></div></div></td><td class="rscore">0.375</td><td class="rscore" id="p7c-siftguard-langgraph" style="color:var(--gray-400)">—</td></tr>
                <tr id="p7r-siftguard-gemini"><td style="font-family:var(--mono);font-size:10px;color:var(--gray-400)">5</td><td style="font-weight:500">Gemini</td><td><span style="color:var(--red);font-family:var(--mono);font-size:12px;font-weight:500">0.250</span></td><td><span style="color:#b06000;font-family:var(--mono);font-size:12px;font-weight:500">0.500</span></td><td><div class="rbar-bg"><div class="rbar-fill" style="width:37.5%"></div></div></td><td class="rscore" style="color:var(--gray-400)">0.375</td><td class="rscore" id="p7c-siftguard-gemini" style="color:var(--gray-400)">—</td></tr>
              </tbody>
            </table>
            <div class="note-warn">ClaudeCode + LangGraph 0.000 on TEST-002 = tool access failure on raw disk image. A single-dataset benchmark ranks them equal to OpenAI FC — they are not. ADR-006 §generalization.</div>
          </div>
        </div>
      </div>

      <!-- P2: Dataset Overview — collapsed -->
      <div class="acc-panel">
        <div class="acc-header" onclick="toggleAcc('acc-p2',this)">
          <div class="acc-hdr-text">
            <div class="acc-title"><span class="acc-num">02</span>Dataset Overview</div>
            <div class="acc-sub">TEST-001 SRL-2018 APT Memory · TEST-002 NIST CFReDS Hacking Case</div>
          </div>
          <svg class="acc-chevron" viewBox="0 0 24 24"><path d="M19 9l-7 7-7-7"/></svg>
        </div>
        <div class="acc-body" id="acc-p2" style="display:none">
          <div class="card"><div class="ds-grid">
            <div class="ds-block"><h4>TEST-001 — SRL-2018</h4><p>Memory image (raw, 5GB). Windows 10 x64. APT hunt. C2 at 172.16.4.10:8080. 4 memory IOCs. 3× F1=1.000. Gemini hallucination confirmed genuine.</p></div>
            <div class="ds-block"><h4>TEST-002 — NIST CFReDS</h4><p>SCHARDT.img NTFS disk. Windows XP. Suspect Greg Schardt / Mr. Evil. 8 disk IOCs. Best: OpenAI FC 0.750. LangGraph + ClaudeCode: tool access failure on raw disk.</p></div>
          </div></div>
        </div>
      </div>

      <!-- P3: Orchestrator Config — collapsed -->
      <div class="acc-panel">
        <div class="acc-header" onclick="toggleAcc('acc-p3',this)">
          <div class="acc-hdr-text">
            <div class="acc-title"><span class="acc-num">03</span>Orchestrator Configuration</div>
            <div class="acc-sub">5 adapters · same MCP tool surface · orchestration/provider stack is the variable</div>
          </div>
          <svg class="acc-chevron" viewBox="0 0 24 24"><path d="M19 9l-7 7-7-7"/></svg>
        </div>
        <div class="acc-body" id="acc-p3" style="display:none">
          <div class="card"><div class="ph-grid">
            <div class="ph-card"><h4>Native Claude</h4><p>Anthropic Messages API · claude-sonnet-4-6 · prompt caching on all 4 endpoints</p></div>
            <div class="ph-card"><h4>OpenAI FC</h4><p>OpenAI function-calling · gpt-5.5 · no temperature param · strongest generalizer</p></div>
            <div class="ph-card"><h4>LangGraph</h4><p>Graph-based · claude-sonnet-4-6 · max_iterations=15 · fails on disk workloads</p></div>
            <div class="ph-card"><h4>Gemini 2.5 Pro</h4><p>google-genai SDK · 1M context · anti-correlated across surfaces · genuine hallucination on TEST-001</p></div>
            <div class="ph-card"><h4>ClaudeCode</h4><p>Headless CLI subprocess · --permission-mode bypassPermissions · stdin=DEVNULL · null result on TEST-002</p></div>
          </div></div>
        </div>
      </div>

      <!-- P4: Evidence Chain — collapsed -->
      <div class="acc-panel">
        <div class="acc-header" onclick="toggleAcc('acc-p4',this)">
          <div class="acc-hdr-text">
            <div class="acc-title"><span class="acc-num">04</span>Evidence Chain</div>
            <div class="acc-sub">Hash verification · timeline reconstruction · artifact provenance</div>
          </div>
          <svg class="acc-chevron" viewBox="0 0 24 24"><path d="M19 9l-7 7-7-7"/></svg>
        </div>
        <div class="acc-body" id="acc-p4" style="display:none">
          <div class="card"><div class="ph-card"><h4>Wired in T15</h4><p>Hash log, artifact manifest, timeline viewer to follow. Methodology SHA: <span class="mono">ed5133e4</span> (TEST-001). SCHARDT.img SHA-256 verified at mount.</p></div></div>
        </div>
      </div>

      <!-- P5: Eval Methodology — collapsed -->
      <div class="acc-panel">
        <div class="acc-header" onclick="toggleAcc('acc-p5',this)">
          <div class="acc-hdr-text">
            <div class="acc-title"><span class="acc-num">05</span>Evaluation Methodology</div>
            <div class="acc-sub">Ground truth v1.1.0 · TP/applicable_count scorer · ADR-009</div>
          </div>
          <svg class="acc-chevron" viewBox="0 0 24 24"><path d="M19 9l-7 7-7-7"/></svg>
        </div>
        <div class="acc-body" id="acc-p5" style="display:none">
          <div class="card">
            <div class="gaps"><strong>Known gap — ADR-009</strong><ul><li>Report-text recall mode active. Field-level IOC provenance: P2 backlog.</li></ul></div>
            <div class="ph-card"><h4>Ground truth v1.1.0</h4><p>TEST-001: 4 memory IOCs (Volatility surface). TEST-002: 8 disk IOCs (filesystem/MFT/registry). Scorer: TP/applicable_count. evidence_location enum enforces surface reachability.</p></div>
          </div>
        </div>
      </div>

      <!-- P6: Known Limitations — collapsed -->
      <div class="acc-panel">
        <div class="acc-header" onclick="toggleAcc('acc-p6',this)">
          <div class="acc-hdr-text">
            <div class="acc-title"><span class="acc-num">06</span>Known Limitations</div>
            <div class="acc-sub">Honest gaps — acknowledged, not hidden · LIMITATIONS.md</div>
          </div>
          <svg class="acc-chevron" viewBox="0 0 24 24"><path d="M19 9l-7 7-7-7"/></svg>
        </div>
        <div class="acc-body" id="acc-p6" style="display:none">
          <div class="card"><div class="ph-grid">
            <div class="ph-card" style="border-color:var(--red)"><h4>Scorer fallback mode</h4><p>Report-text recall path active. ADR-009 — resolve in T15.</p></div>
            <div class="ph-card" style="border-color:var(--amber)"><h4>LangGraph + ClaudeCode 0.000 on TEST-002</h4><p>Tool config failure on raw disk image. Max iterations hit. ADR-006.</p></div>
            <div class="ph-card"><h4>Storage-layer audit hardening</h4><p>SQLite triggers + row-chain SHA-256 are post-hackathon. Boundary is application-layer SnapshotWriter. LIMITATIONS.md §3.4.</p></div>
            <div class="ph-card"><h4>OS-level isolation</h4><p>Orchestrators and MCP server share user privilege domain. Production: separate users + read-only evidence mounts. THREAT_MODEL.md §5.</p></div>
          </div></div>
        </div>
      </div>

    </div><!-- /results-accordion -->

    <!-- P8: Spoliation -->"""

html = replace_once(html, OLD_PANELS, NEW_PANELS, "P1+P7+P2-P6 → accordion")

# ── 9. Fix P8 header (P0-B miss in dashboard) ────────────────────────────────
html = replace_once(
    html,
    "<p>Append-only audit DB moat · triggered mutation blocks logged immutably</p>",
    "<p>Application-layer write discipline · blocked mutation receipts logged · 15/15 spoliation tests green</p>",
    "p8 header",
)
html = replace_once(
    html,
    '<p><strong>Append-only guarantee:</strong> All writes to <span class="cpill">audit_events</span> and <span class="cpill">evidence_chain</span> pass through <span class="cpill">trg_immutable_audit</span>. Any mutation triggers immediate rollback — that event is itself immutable.</p>',
    '<p><strong>Application-layer discipline:</strong> All audit writes route through <span class="cpill">SnapshotWriter</span>. No UPDATE or DELETE surface is exposed. Storage-layer trigger hardening documented in <span class="cpill">LIMITATIONS.md</span> \u00a7\u00a73.4.</p>',
    "p8 note-info",
)

# ── 10. JS: add toggleAcc ─────────────────────────────────────────────────────
ACC_JS = """function toggleAcc(id, hdr) {
  const body = document.getElementById(id);
  if (!body) return;
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : 'block';
  if (hdr) {
    hdr.classList.toggle('open', !open);
    const chev = hdr.querySelector('.acc-chevron');
    if (chev) chev.classList.toggle('open', !open);
  }
}

"""
html = replace_once(
    html, "function setMode(mode) {", ACC_JS + "function setMode(mode) {", "toggleAcc JS"
)

# ── 11. JS: update setMode ────────────────────────────────────────────────────
OLD_SET_MODE = """function setMode(mode) {
  document.body.className = 'mode-' + mode;
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
  if (mode === 'results') {
    if (document.getElementById('p0').classList.contains('active')) {
      const p1Nav = document.querySelector('.nav-item[data-panel="p1"]');
      showPanel('p1', p1Nav);
    }
  } else {
    const p0Nav = document.querySelector('.nav-item[data-panel="p0"]');
    showPanel('p0', p0Nav);
  }
}"""
NEW_SET_MODE = """function setMode(mode) {
  document.body.className = 'mode-' + mode;
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
  const accordion = document.getElementById('results-accordion');
  if (mode === 'results') {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    if (accordion) accordion.style.display = 'block';
  } else {
    if (accordion) accordion.style.display = 'none';
    const p0Nav = document.querySelector('.nav-item[data-panel="p0"]');
    showPanel('p0', p0Nav);
  }
}"""
html = replace_once(html, OLD_SET_MODE, NEW_SET_MODE, "setMode update")

# ── 12. JS: update showPanel to handle accordion ─────────────────────────────
OLD_SHOW = """function showPanel(id, el) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
  if (id === 'p9') initIOC();
  if (id === 'p7') loadP7Corrections();
}"""
NEW_SHOW = """function showPanel(id, el) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const panel = document.getElementById(id);
  if (panel) panel.classList.add('active');
  if (el && el.classList) el.classList.add('active');
  const accordion = document.getElementById('results-accordion');
  if (accordion) accordion.style.display = (id === 'p8' || id === 'p9') ? 'none' : '';
  if (id === 'p9') initIOC();
}"""
html = replace_once(html, OLD_SHOW, NEW_SHOW, "showPanel update")

# ── 13. Footer: update tag ────────────────────────────────────────────────────
html = replace_once(html, "T14 · Due June 15", "T14 ✓ · T15 next", "footer tag")

# ── Write ─────────────────────────────────────────────────────────────────────
INDEX.write_text(html)
print(f"\nDone. {original_len} → {len(html)} chars ({len(html) - original_len:+d})")
print("Next: open http://localhost:8080 — P1+P7 expanded, P2-P6 collapsed one-click.")
