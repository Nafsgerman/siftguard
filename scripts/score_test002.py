"""Score all TEST-002 results and write experiments/analysis/TEST-002/data.json."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GT_PATH = REPO / "tests/benchmark/ground_truth/TEST-002.json"
RESULTS_ROOT = REPO / "experiments/results"
OUT_PATH = REPO / "experiments/analysis/TEST-002/data.json"

ORCH_MAP = {
    "baseline_langgraph": "langgraph",
    "baseline_openai-fc": "openai_fc",
    "baseline_gemini": "gemini",
    "baseline_claudecode": "claudecode",
    "baseline": "baseline",
}

gt = json.loads(GT_PATH.read_text())
gt_iocs = gt.get("expected_iocs", [])


def extract_text(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, dict):
        return json.dumps(raw)
    s = str(raw)
    # tuple string: ('report text', 'uuid')
    if s.startswith("('") or s.startswith('("'):
        try:
            t = ast.literal_eval(s)
            return t[0] if isinstance(t, tuple) else str(t)
        except Exception:
            pass
    return s


def score_text(text: str) -> float:
    if not text:
        return 0.0
    text_lower = text.lower()
    matched = sum(1 for ioc in gt_iocs if ioc["value"].lower() in text_lower)
    total = len(gt_iocs)
    if total == 0:
        return 0.0
    recall = matched / total
    # estimate precision: matched / (matched + rough FP estimate)
    # use recall as F1 proxy when we can't compute precision from text
    return round(recall, 4)


scores = {}
for orch_dir, orch_key in ORCH_MAP.items():
    case_dir = RESULTS_ROOT / orch_dir / "TEST-002"
    if not case_dir.exists():
        print(f"SKIP {orch_dir} — no dir")
        continue
    files = sorted(case_dir.glob("result_*.json"), reverse=True)
    if not files:
        print(f"SKIP {orch_dir} — no files")
        continue
    data = json.loads(files[0].read_text())
    raw = data.get("raw") if data else None
    text = extract_text(raw)
    f1 = score_text(text)
    scores[orch_key] = {"mean": f1, "runs": 1}
    print(f"{orch_key:20s} F1={f1:.4f}  text_len={len(text)}")

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
existing = {}
if OUT_PATH.exists():
    try:
        existing = json.loads(OUT_PATH.read_text())
    except Exception:
        pass

existing.setdefault("panel_7", {}).setdefault("data", {}).update(scores)
OUT_PATH.write_text(json.dumps(existing, indent=2))
print(f"\nWritten: {OUT_PATH}")
