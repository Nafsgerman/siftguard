#!/usr/bin/env python3
"""
T13: Score all 5 orchestrators against TEST-001 using report-text scorer.
Zero API cost — reads existing result_*.json files.
Writes real F1 to experiments/analysis/TEST-001/data.json.
Prints delta table: proxy (old) vs real (new).
"""
from __future__ import annotations
import json
import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS_ROOT = REPO / "experiments" / "results"
GT_ROOT = REPO / "experiments" / "ground_truth"
ANALYSIS_OUT = REPO / "experiments" / "analysis" / "TEST-001" / "data.json"

AGENT_MAP = {
    "baseline_v2":        "siftguard-v2",
    "baseline_langgraph": "siftguard-langgraph",
    "baseline_openai-fc": "siftguard-openai-fc",
    "baseline_gemini":    "siftguard-gemini",
    "baseline_claudecode":"siftguard-claudecode",
}

LABEL_MAP = {
    "siftguard-v2":          "Native Loop   ",
    "siftguard-langgraph":   "LangGraph     ",
    "siftguard-openai-fc":   "OpenAI FC     ",
    "siftguard-gemini":      "Gemini        ",
    "siftguard-claudecode":  "Claude Code   ",
}

GT_VERSION = "1.1.0"
CASE_ID = "TEST-001"


def load_gt_iocs() -> list[str]:
    gt_file = GT_ROOT / f"{CASE_ID}-v{GT_VERSION}.json"
    gt = json.loads(gt_file.read_text())
    return [ioc["value"].lower() for ioc in gt.get("iocs", [])]


def score_report_text(text: str, ioc_values: list[str]) -> tuple[float | None, int, int]:
    if not ioc_values:
        return None, 0, 0
    text_lower = text.lower()
    tp = sum(1 for v in ioc_values if v in text_lower)
    fn = len(ioc_values) - tp
    return tp / len(ioc_values), tp, fn


def extract_report_text(result) -> str:
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return str(result)
    for key in ("report", "raw", "output", "final_report"):
        val = result.get(key)
        if isinstance(val, str) and len(val) > 100:
            return val
    for key in ("result", "data"):
        val = result.get(key)
        if isinstance(val, dict):
            for sub in ("report", "raw", "output"):
                s = val.get(sub)
                if isinstance(s, str) and len(s) > 100:
                    return s
    for key in ("raw", "output"):
        val = result.get(key)
        if isinstance(val, str) and val.startswith("('"):
            try:
                t = ast.literal_eval(val)
                if isinstance(t, tuple) and isinstance(t[0], str):
                    return t[0]
            except Exception:
                pass
    return json.dumps(result)


def find_latest_result(config_dir: str) -> Path | None:
    case_path = RESULTS_ROOT / config_dir / CASE_ID
    if not case_path.exists():
        return None
    files = sorted(
        [f for f in case_path.glob("result_*.json") if ".score." not in f.name],
        reverse=True,
    )
    return files[0] if files else None


def read_existing_data() -> dict:
    if ANALYSIS_OUT.exists():
        try:
            return json.loads(ANALYSIS_OUT.read_text())
        except Exception:
            pass
    return {}


def write_agent_score(data: dict, agent_id: str, f1: float | None,
                      tp: int, fn: int, timestamp: str) -> None:
    p7 = data.setdefault("panel_7", {}).setdefault("data", {})
    block = p7.setdefault(agent_id, {"runs": [], "mean": None, "n": 0})
    block["runs"] = [r for r in block.get("runs", []) if r.get("timestamp") != timestamp]
    block["runs"].append({"f1": f1, "timestamp": timestamp, "gt_version": GT_VERSION,
                          "applicable_count": 4, "tp": tp, "fn": fn})
    valid = [r["f1"] for r in block["runs"] if r.get("f1") is not None]
    block["mean"] = round(sum(valid) / len(valid), 4) if valid else None
    block["n"] = len(valid)
    block.setdefault("case_scores", {})[CASE_ID] = f1
    ANALYSIS_OUT.parent.mkdir(parents=True, exist_ok=True)
    ANALYSIS_OUT.write_text(json.dumps(data, indent=2))


def main():
    ioc_values = load_gt_iocs()
    print(f"\nGround truth IOCs ({len(ioc_values)}): {ioc_values}")
    data = read_existing_data()
    missing: list[str] = []

    header = f"{'Agent':<18} {'File':<44} {'TP':>4} {'FN':>4} {'F1':>8}  Status"
    sep = "=" * len(header)
    print(f"\n{sep}\nT13 — Real Scorer (TEST-001, report-text)\n{sep}\n{header}\n{'-'*len(header)}")

    for config_dir, agent_id in AGENT_MAP.items():
        label = LABEL_MAP[agent_id]
        result_path = find_latest_result(config_dir)
        if result_path is None:
            print(f"{label} {'<no result file>':<44} {'—':>4} {'—':>4} {'—':>8}  NEEDS RUN")
            missing.append(agent_id)
            continue
        result = json.loads(result_path.read_text())
        text = extract_report_text(result)
        timestamp = result_path.stem.replace("result_", "")
        f1, tp, fn = score_report_text(text, ioc_values)
        f1_str = f"{f1:.3f}" if f1 is not None else "None"
        print(f"{label} {result_path.name:<44} {tp:>4} {fn:>4} {f1_str:>8}  OK")
        write_agent_score(data, agent_id, f1, tp, fn, timestamp)

    print(sep)

    cost_map = {"siftguard-v2":0.05,"siftguard-langgraph":0.10,
                "siftguard-openai-fc":0.25,"siftguard-gemini":0.05,"siftguard-claudecode":0.65}
    if missing:
        total = sum(cost_map.get(a, 0.20) for a in missing)
        print(f"\n⚠ {len(missing)} agent(s) need TEST-001 re-runs:")
        for a in missing:
            print(f"  - {LABEL_MAP[a].strip():<18} ~${cost_map.get(a,0.20):.2f}")
        print(f"  Total: ~${total:.2f}  >>> confirm before triggering <<<")
    else:
        print(f"\n✅ All agents scored. Written → {ANALYSIS_OUT}")

    proxy_map = {"siftguard-v2":"1.000","siftguard-langgraph":"?",
                 "siftguard-openai-fc":"?","siftguard-gemini":"?","siftguard-claudecode":"?"}
    print(f"\n{'Agent':<18} {'Proxy F1':>10} {'Real F1':>10} {'Delta':>8}")
    print("-" * 50)
    p7d = data.get("panel_7", {}).get("data", {})
    for agent_id, label in LABEL_MAP.items():
        proxy = proxy_map.get(agent_id, "?")
        real = p7d.get(agent_id, {}).get("mean")
        real_str = f"{real:.3f}" if real is not None else "pending"
        try:
            delta = f"{real - float(proxy):+.3f}" if real is not None and proxy != "?" else "—"
        except Exception:
            delta = "—"
        print(f"{label} {proxy:>10} {real_str:>10} {delta:>8}")


if __name__ == "__main__":
    main()
