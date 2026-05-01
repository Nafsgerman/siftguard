"""
SIFTGuard Benchmark Scorer
Computes precision, recall, F1 for IOC detection and section completeness.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class IOCScore:
    ioc_type: str
    ioc_value: str
    expected_confidence: str
    found: bool = False
    found_in_section: str = ""


@dataclass
class BenchmarkScore:
    case_id: str
    threat_type: str
    # IOC detection
    ioc_scores: list[IOCScore] = field(default_factory=list)
    # Section completeness
    sections_found: list[str] = field(default_factory=list)
    sections_missing: list[str] = field(default_factory=list)
    # Verdict keywords
    verdict_keywords_found: list[str] = field(default_factory=list)
    verdict_keywords_missing: list[str] = field(default_factory=list)
    # Boolean flags
    persistence_detected: bool = False
    lateral_movement_detected: bool = False
    timestomp_detected: bool = False
    code_injection_detected: bool = False

    @property
    def ioc_precision(self) -> float:
        found = [s for s in self.ioc_scores if s.found]
        high_conf = [s for s in self.ioc_scores if s.expected_confidence == "high"]
        if not high_conf:
            return 1.0
        found_high = [s for s in found if s.expected_confidence == "high"]
        return len(found_high) / len(high_conf)

    @property
    def ioc_recall(self) -> float:
        if not self.ioc_scores:
            return 0.0
        return sum(1 for s in self.ioc_scores if s.found) / len(self.ioc_scores)

    @property
    def ioc_f1(self) -> float:
        p, r = self.ioc_precision, self.ioc_recall
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    @property
    def section_score(self) -> float:
        total = len(self.sections_found) + len(self.sections_missing)
        if total == 0:
            return 1.0
        return len(self.sections_found) / total

    @property
    def verdict_score(self) -> float:
        total = len(self.verdict_keywords_found) + len(self.verdict_keywords_missing)
        if total == 0:
            return 1.0
        return len(self.verdict_keywords_found) / total

    @property
    def overall_score(self) -> float:
        """Weighted composite: IOC F1 (50%) + sections (25%) + verdict (25%)"""
        return (self.ioc_f1 * 0.50) + (self.section_score * 0.25) + (self.verdict_score * 0.25)

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "threat_type": self.threat_type,
            "scores": {
                "ioc_precision": round(self.ioc_precision, 3),
                "ioc_recall": round(self.ioc_recall, 3),
                "ioc_f1": round(self.ioc_f1, 3),
                "section_completeness": round(self.section_score, 3),
                "verdict_accuracy": round(self.verdict_score, 3),
                "overall": round(self.overall_score, 3),
            },
            "ioc_details": [
                {
                    "type": s.ioc_type,
                    "value": s.ioc_value,
                    "confidence": s.expected_confidence,
                    "found": s.found,
                    "found_in": s.found_in_section,
                }
                for s in self.ioc_scores
            ],
            "sections_found": self.sections_found,
            "sections_missing": self.sections_missing,
            "verdict_keywords_found": self.verdict_keywords_found,
            "verdict_keywords_missing": self.verdict_keywords_missing,
            "flags": {
                "persistence_detected": self.persistence_detected,
                "lateral_movement_detected": self.lateral_movement_detected,
                "timestomp_detected": self.timestomp_detected,
                "code_injection_detected": self.code_injection_detected,
            },
        }


def score_report(report_text: str, ground_truth: dict) -> BenchmarkScore:
    """
    Score an agent-generated incident report against ground truth.
    """
    report_lower = report_text.lower()
    score = BenchmarkScore(
        case_id=ground_truth["case_id"],
        threat_type=ground_truth["threat_type"],
    )

    # --- IOC detection ---
    for ioc in ground_truth.get("expected_iocs", []):
        ioc_val_lower = ioc["value"].lower()
        found = ioc_val_lower in report_lower
        found_section = ""
        if found:
            # Find which section contains the IOC
            for section in ["executive summary", "indicators of compromise",
                            "timeline", "persistence", "recommendations"]:
                idx = report_lower.find(f"## {section}")
                if idx == -1:
                    continue
                next_section = report_lower.find("## ", idx + 3)
                chunk = report_lower[idx: next_section if next_section > 0 else len(report_lower)]
                if ioc_val_lower in chunk:
                    found_section = section
                    break
        score.ioc_scores.append(IOCScore(
            ioc_type=ioc["type"],
            ioc_value=ioc["value"],
            expected_confidence=ioc["confidence"],
            found=found,
            found_in_section=found_section,
        ))

    # --- Section completeness ---
    for section in ground_truth.get("required_sections", []):
        if f"## {section}".lower() in report_lower:
            score.sections_found.append(section)
        else:
            score.sections_missing.append(section)

    # --- Verdict keywords ---
    for kw in ground_truth.get("expected_verdict_keywords", []):
        if kw.lower() in report_lower:
            score.verdict_keywords_found.append(kw)
        else:
            score.verdict_keywords_missing.append(kw)

    # --- Boolean flags ---
    persistence_terms = ["persist", "run key", "startup", "service", "scheduled task", "registry"]
    score.persistence_detected = any(t in report_lower for t in persistence_terms)

    lateral_terms = ["lateral", "psexec", "wmi", "remote", "pivot", "spread"]
    score.lateral_movement_detected = any(t in report_lower for t in lateral_terms)

    timestomp_terms = ["timestomp", "timestamp", "mft", "fn timestamps", "si timestamps"]
    score.timestomp_detected = any(t in report_lower for t in timestomp_terms)

    injection_terms = ["inject", "malfind", "hollow", "dll injection", "shellcode"]
    score.code_injection_detected = any(t in report_lower for t in injection_terms)

    return score


def load_ground_truth(case_id: str) -> dict:
    gt_dir = Path(__file__).parent / "ground_truth"
    gt_file = gt_dir / f"{case_id}.json"
    if not gt_file.exists():
        raise FileNotFoundError(f"No ground truth for case {case_id} at {gt_file}")
    return json.loads(gt_file.read_text())


def score_from_files(report_path: str, case_id: str) -> BenchmarkScore:
    """Score a saved report file against ground truth."""
    report_text = Path(report_path).read_text()
    gt = load_ground_truth(case_id)
    return score_report(report_text, gt)