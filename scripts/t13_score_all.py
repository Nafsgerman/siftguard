#!/usr/bin/env python3
"""T13: Score all 5 orchestrators against TEST-001. Zero API cost for existing runs."""
from __future__ import annotations
import ast, json
from pathlib import Path

REPO         = Path(__file__).resolve().parent.parent
RESULTS_ROOT = REPO / "experiments" / "results"
GT_ROOT      = REPO / "experiments" / "ground_truth"
ANALYSIS_OUT = REPO / "experiments" / "analysis" / "TEST-001" / "data.json"
CASE_ID      = "TEST-001"
GT_VERSION   = "1.1.0"

AGENT_MAP = {
    "baseline_v2":         "siftguard-v2",
    "baseline_langgraph":  "siftguard-langgraph",
    "baseline_openai-fc":  "siftguard-openai-fc",
    "baseline_gemini":     "siftguard-gemini",
    "baseline_claudecode": "siftguard-claudecode",
}
LABEL_MAP = {
    "siftguard-v2":          "Native Loop  ",
    "siftguard-langgraph":   "LangGraph    ",
    "siftguard-openai-fc":   "OpenAI FC    ",
    "siftguard-gemini":      "Gemini       ",
    "siftguard-claudecode":  "Claude Code  ",
}
COST_MAP = {
    "siftguard-v2": 0.05, "siftguard-langgraph": 0.10,
    "siftguard-openai-fc": 0.25, "siftguard-gemini": 0.05,
    "siftguard-claudecode": 0.65,
}
PROXY_MAP = {
    "siftguard-v2": "1.000", "siftguard-langgraph": "?",
    "siftguard-openai-fc": "?", "siftguard-gemini": "?",
    "siftguard-claudecode": "?",
}


def load_gt_iocs() -> list[str]:
    gt = json.loads((GT_ROOT / f"{CASE_ID}-v{GT_VERSION}.json").read_text())
    return [ioc["value"].lower() for ioc in gt.get("iocs", [])]


def score_text(text: str, iocs: list[str]) -> tuple[float, int, int]:
    tl = text.lower()
    tp = sum(1 for v in iocs if v in tl)
    fn = len(iocs) - tp
    return (tp / len(iocs) if iocs else 0.0), tp, fn


def best_text(config_dir: str) -> tuple[str, str]:
    """Return (best_text, filename) for scoring. Prefers .md report, falls back to result JSON."""
    case_path = RESULTS_ROOT / config_dir / CASE_ID
    if not case_path.exists():
        return "", ""

    # Try latest result JSON → find paired .md
    result_files = sorted(
        [f for f in case_path.glob("result_*.json") if ".score." not in f.name],
        reverse=True,
    )
    if not result_files:
        return "", ""

    result_path = result_files[0]
    ts = result_path.stem.replace("result_", "")

    # Prefer paired .md
    md = result_path.parent / f"report_{ts}.md"
    if not md.exists():
        mds = sorted(case_path.glob("report_*.md"), reverse=True)
        md = mds[0] if mds else None

    if md and md.exists():
        return md.read_text(), md.name

    # Fall back: extract text from JSON
    raw = result_path.read_text()
    try:
        data = json.loads(raw)
        if isinstance(data, str):
            return data, result_path.name
        for key in ("report", "raw", "output", "final_report"):
            val = data.get(key, "")
            if isinstance(val, str) and len(val) > 200:
                return val, result_path.name
        for key in ("raw", "output"):
            val = data.get(key, "")
            if isinstance(val, str) and val.startswith("('"):
                try:
                    t = ast.literal_eval(val)
                    if isinstance(t, tuple) and isinstance(t[0], str):
                        return t[0], result_path.name
                except Exception:
                    pass
        return raw, result_path.name
    except Exception:
        return raw, result_path.name


def read_data() -> dict:
    if ANALYSIS_OUT.exists():
        try:
            return json.loads(ANALYSIS_OUT.read_text())
        except Exception:
            pass
    return {}


def write_score(data: dict, agent_id: str, f1: float, tp: int, fn: int, ts: str) -> None:
    p7 = data.setdefault("panel_7", {}).setdefault("data", {})
    blk = p7.setdefault(agent_id, {"runs": [], "mean": None, "n": 0})
    blk["runs"] = [r for r in blk.get("runs", []) if r.get("timestamp") != ts]
    blk["runs"].append({"f1": f1, "timestamp": ts, "gt_version": GT_VERSION,
                        "applicable_count": 4, "tp": tp, "fn": fn})
    valid = [r["f1"] for r in blk["runs"] if r.get("f1") is not None]
    blk["mean"] = round(sum(valid) / len(valid), 4) if valid else None
    blk["n"] = len(valid)
    blk.setdefault("case_scores", {})[CASE_ID] = f1
    ANALYSIS_OUT.parent.mkdir(parents=True, exist_ok=True)
    ANALYSIS_OUT.write_text(json.dumps(data, indent=2))


def main() -> None:
    iocs = load_gt_iocs()
    print(f"\nGround truth IOCs ({len(iocs)}): {iocs}")
    data = read_data()
    missing: list[str] = []

    W = 100
    print(f"\n{'='*W}")
    print("T13 — Real Scorer (TEST-001, report-text)")
    print(f"{'='*W}")
    print(f"{'Agent':<16} {'File':<42} {'TP':>4} {'FN':>4} {'F1':>8}  Status")
    print(f"{'-'*W}")

    for config_dir, agent_id in AGENT_MAP.items():
        label = LABEL_MAP[agent_id]
        text, fname = best_text(config_dir)

        if not text:
            print(f"{label} {'<no result file>':<42} {'—':>4} {'—':>4} {'—':>8}  NEEDS RUN")
            missing.append(agent_id)
            continue

        f1, tp, fn = score_text(text, iocs)
        ts = fname.replace("report_", "").replace("result_", "").replace(".md", "").replace(".json", "")
        print(f"{label} {fname:<42} {tp:>4} {fn:>4} {f1:>8.3f}  OK")
        write_score(data, agent_id, f1, tp, fn, ts)

    print(f"{'='*W}")

    if missing:
        total = sum(COST_MAP.get(a, 0.20) for a in missing)
        print(f"\n⚠  {len(missing)} agent(s) need TEST-001 re-runs:")
        for a in missing:
            print(f"   - {LABEL_MAP[a].strip():<16} ~${COST_MAP.get(a, 0.20):.2f}")
        print(f"   Total: ~${total:.2f}  >>> confirm before triggering <<<")
    else:
        print(f"\n✅ All agents scored. Written → {ANALYSIS_OUT}")

    p7d = data.get("panel_7", {}).get("data", {})
    print(f"\n{'Agent':<16} {'Proxy F1':>10} {'Real F1':>10} {'Delta':>8}")
    print("-" * 48)
    for agent_id, label in LABEL_MAP.items():
        proxy = PROXY_MAP.get(agent_id, "?")
        real  = p7d.get(agent_id, {}).get("mean")
        rs    = f"{real:.3f}" if real is not None else "pending"
        try:
            delta = f"{real - float(proxy):+.3f}" if real is not None and proxy != "?" else "—"
        except Exception:
            delta = "—"
        print(f"{label} {proxy:>10} {rs:>10} {delta:>8}")


if __name__ == "__main__":
    main()