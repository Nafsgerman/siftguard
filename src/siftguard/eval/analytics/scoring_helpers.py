"""Shared scoring helpers — extracted from panel_6_ablation to avoid duplication.

Used by: panel_6_ablation, panel_6b_stability.
"""
from __future__ import annotations

import json
from pathlib import Path

from siftguard.eval.analytics.load_traces import load_iteration_snapshots
from siftguard.eval.analytics.scorer_framework import score_findings
from siftguard.eval.trace import Finding, FindingType

RES_DIR = Path(__file__).resolve().parents[4] / "experiments" / "results"
GT_DIR  = Path(__file__).resolve().parents[4] / "tests" / "benchmark" / "ground_truth"


def score_run_from_db(run: dict, db_path: Path, gt_path: Path) -> float:
    """Score a run dict (from experiment_run table) against ground truth. Returns IOC F1."""
    run_id = run["run_id"]
    snapshots = load_iteration_snapshots(db_path, run_id)
    if not snapshots:
        return 0.0
    last = snapshots[-1]
    raw_list = json.loads(last.get("findings_json") or "[]")
    findings = []
    seen: set[tuple] = set()
    valid_types = {t.value for t in FindingType}
    for raw in raw_list:
        ftype_str = raw.get("type", "other")
        if ftype_str not in valid_types:
            ftype_str = "other"
        value = str(raw.get("value", ""))
        key = (ftype_str, value.lower())
        if key in seen:
            continue
        seen.add(key)
        excerpt = str(raw.get("evidence_excerpt", value))[:200]
        if len(excerpt) < 10:
            excerpt = (excerpt + " " * 10)[:10]
        findings.append(Finding(
            id=raw.get("id", f"{ftype_str}-{value}"),
            type=FindingType(ftype_str),
            value=value,
            confidence=raw.get("confidence"),
            supporting_audit_entry_ids=[],
            evidence_excerpt=excerpt,
            first_seen_iteration=raw.get("first_seen_iteration", 0),
        ))
    return score_findings(findings, gt_path).f1


def score_run_from_report(config_name: str, case_id: str, gt_path: Path) -> float:
    """Score the latest saved report for a config+case against ground truth. Returns IOC F1."""
    result_dir = RES_DIR / config_name / case_id
    if not result_dir.exists():
        return 0.0
    files = sorted(result_dir.glob("result_*.json"), reverse=True)
    result = None
    for f in files:
        try:
            data = json.loads(f.read_text())
            if data.get("status") == "ok":
                result = data
                break
        except Exception:
            continue
    if not result or not result.get("report"):
        return 0.0
    try:
        report_path = Path(result["report"])
        if not report_path.exists():
            return 0.0
        text = report_path.read_text()
        ioc_section = ""
        in_ioc = False
        for line in text.splitlines():
            if line.strip().startswith("## Indicators"):
                in_ioc = True
                continue
            if in_ioc and line.strip().startswith("## "):
                break
            if in_ioc:
                ioc_section += line + "\n"
        if not ioc_section:
            ioc_section = text
        gt = json.loads(gt_path.read_text())
        gt_iocs = gt.get("expected_iocs", [])
        valid_types = {t.value for t in FindingType}
        findings = []
        matched_gt: set[str] = set()
        for ioc in gt_iocs:
            val = ioc["value"].lower()
            if val in ioc_section.lower() and val not in matched_gt:
                matched_gt.add(val)
                ftype_str = ioc["type"] if ioc["type"] in valid_types else "other"
                excerpt = (val + " " * 10)[:10]
                findings.append(Finding(
                    id=f"v1-match-{val}",
                    type=FindingType(ftype_str),
                    value=ioc["value"],
                    confidence=None,
                    supporting_audit_entry_ids=[],
                    evidence_excerpt=excerpt,
                    first_seen_iteration=0,
                ))
        return score_findings(findings, gt_path).f1
    except Exception:
        return 0.0


def score_seed_results(seed_results: list[dict], config_name: str, case_id: str, gt_path: Path) -> list[float]:
    """Extract F1 scores from a list of seed result dicts (from ablation_v2 dir)."""
    scores = []
    for r in seed_results:
        if r.get("status") != "ok":
            continue
        report = r.get("report", "")
        if report:
            f1 = score_run_from_report(config_name, case_id, gt_path)
            scores.append(f1)
    return scores