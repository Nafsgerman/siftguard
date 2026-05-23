"""Score TEST-002 results against v1.1.0 ground truth (8 disk IOCs).

Reads each orchestrator's most recent result, extracts report text from either
`raw` (tuple-string format) or `report` (filesystem path), and computes recall
against the v1.1.0 IOC list. Writes panel_7 entries to experiments/analysis/TEST-002/data.json.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GT_PATH = REPO / "experiments" / "ground_truth" / "TEST-002-v1.1.0.json"
RESULTS_ROOT = REPO / "experiments" / "results"
OUT_PATH = REPO / "experiments" / "analysis" / "TEST-002" / "data.json"

ORCH_MAP = {
    "baseline": "siftguard-v2",
    "baseline_langgraph": "siftguard-langgraph",
    "baseline_openai-fc": "siftguard-openai-fc",
    "baseline_gemini": "siftguard-gemini",
    "baseline_claudecode": "siftguard-claudecode",
}

gt = json.loads(GT_PATH.read_text())
gt_iocs = gt["iocs"]
GT_VERSION = gt["version"]
APPLICABLE = len(gt_iocs)


def extract_text(data: dict) -> str:
    """Pull report text from either `raw` (tuple-string) or `report` (path)."""
    if not data:
        return ""

    # baseline/Native shape: {"report": "/path/to/report.md"}
    report_path = data.get("report")
    if report_path:
        # path is from VM (/cases/...) — map to local
        local = str(report_path).replace("/cases/TEST-001/siftguard/", str(REPO) + "/")
        p = Path(local)
        if p.exists():
            return p.read_text()
        # fallback: try filename in same dir as result json
        return ""

    # adapter shape: {"raw": "('report text', 'uuid')"}
    raw = data.get("raw")
    if raw is None:
        return ""
    s = str(raw)
    if s.startswith("('") or s.startswith('("'):
        try:
            t = ast.literal_eval(s)
            return t[0] if isinstance(t, tuple) else str(t)
        except Exception:
            return s
    return s


def score_text(text: str) -> tuple[float, list[str], list[str]]:
    """Return (recall, hits, misses) — hits/misses are ioc_id lists."""
    if not text:
        return 0.0, [], [ioc["ioc_id"] for ioc in gt_iocs]
    text_lower = text.lower()
    hits, misses = [], []
    for ioc in gt_iocs:
        if ioc["value"].lower() in text_lower:
            hits.append(ioc["ioc_id"])
        else:
            misses.append(ioc["ioc_id"])
    return round(len(hits) / APPLICABLE, 4), hits, misses


print(f"Ground truth: TEST-002 v{GT_VERSION} — {APPLICABLE} applicable IOCs")
print("=" * 72)

panel_data: dict[str, dict] = {}
detail_rows: list[dict] = []

for orch_dir, agent_id in ORCH_MAP.items():
    case_dir = RESULTS_ROOT / orch_dir / "TEST-002"
    if not case_dir.exists():
        print(f"SKIP {orch_dir:25s} — no dir")
        continue

    # Pick most recent result_*.json
    files = sorted(case_dir.glob("result_*.json"), reverse=True)
    if not files:
        print(f"SKIP {orch_dir:25s} — no result files")
        continue

    latest = files[0]
    data = json.loads(latest.read_text())
    if data is None:
        print(f"NULL {orch_dir:25s} — result is null (run produced no output)")
        f1, hits, misses = 0.0, [], [ioc["ioc_id"] for ioc in gt_iocs]
        text_len = 0
    else:
        text = extract_text(data)
        text_len = len(text)
        f1, hits, misses = score_text(text)

    timestamp = latest.stem.replace("result_", "")
    panel_data[agent_id] = {
        "runs": [
            {
                "f1": f1,
                "timestamp": timestamp,
                "gt_version": GT_VERSION,
                "applicable_count": APPLICABLE,
            }
        ],
        "mean": f1,
        "n": 1,
        "case_scores": {"TEST-002": f1},
    }
    detail_rows.append(
        {
            "agent_id": agent_id,
            "f1": f1,
            "tp": len(hits),
            "fn": len(misses),
            "hits": hits,
            "misses": misses,
            "text_len": text_len,
            "source_file": str(latest.relative_to(REPO)),
        }
    )
    print(f"{agent_id:28s} F1={f1:.4f}  TP={len(hits)}/{APPLICABLE}  text_len={text_len}")

# Write panel_7 data
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
existing = {}
if OUT_PATH.exists():
    try:
        existing = json.loads(OUT_PATH.read_text())
    except Exception:
        pass

existing.setdefault("panel_7", {}).setdefault("data", {})
existing["panel_7"]["data"] = panel_data
existing["panel_7"]["gt_version"] = GT_VERSION
existing["panel_7"]["applicable_count"] = APPLICABLE
existing["panel_7"]["detail"] = detail_rows

OUT_PATH.write_text(json.dumps(existing, indent=2))
print()
print(f"Written: {OUT_PATH.relative_to(REPO)}")
