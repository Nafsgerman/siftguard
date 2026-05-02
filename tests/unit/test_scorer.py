"""Unit tests for the benchmark scorer."""
from __future__ import annotations
import pytest
from tests.benchmark.scorer import score_report, BenchmarkScore

GROUND_TRUTH = {
    "case_id": "TEST-UNIT",
    "threat_type": "apt_c2",
    "expected_iocs": [
        {"type": "process", "value": "usbclient.exe", "confidence": "high"},
        {"type": "ip", "value": "172.16.4.4", "confidence": "high"},
        {"type": "technique", "value": "T1071", "confidence": "medium"},
    ],
    "expected_persistence": True,
    "expected_lateral_movement": False,
    "expected_timestomp": False,
    "expected_code_injection": False,
    "expected_verdict_keywords": ["usbclient", "172.16.4.4", "suspicious"],
    "required_sections": [
        "Executive Summary",
        "Timeline of Events",
        "Indicators of Compromise",
        "Persistence Mechanisms",
        "Recommendations",
        "Evidence References",
    ],
}

PERFECT_REPORT = """
## Executive Summary
Analysis confirms APT compromise via usbclient.exe. C2 communication to 172.16.4.4. Suspicious activity detected with persistence mechanisms.

## Timeline of Events
- 2018-09-06 17:08 - usbclient.exe spawned from explorer.exe
- 2018-09-06 17:13 - C2 connection to 172.16.4.4:8080 established

## Indicators of Compromise
- Process: usbclient.exe (PID 6648)
- IP: 172.16.4.4 (C2 server)
- Technique: T1071

## Persistence Mechanisms
Registry run key modification detected. Persistence established via startup entry.

## Recommendations
1. Isolate affected system
2. Block 172.16.4.4 at firewall

## Evidence References
- memory.img: vol_pslist, vol_netscan
"""

EMPTY_REPORT = ""


def test_perfect_report_scores_high():
    score = score_report(PERFECT_REPORT, GROUND_TRUTH)
    assert score.overall_score >= 0.8
    assert score.section_score == 1.0
    assert score.ioc_f1 >= 0.6


def test_empty_report_scores_zero():
    score = score_report(EMPTY_REPORT, GROUND_TRUTH)
    assert score.overall_score == 0.0
    assert score.ioc_recall == 0.0
    assert score.section_score == 0.0


def test_ioc_detection():
    score = score_report(PERFECT_REPORT, GROUND_TRUTH)
    found = [s for s in score.ioc_scores if s.found]
    assert any(s.ioc_value == "usbclient.exe" for s in found)
    assert any(s.ioc_value == "172.16.4.4" for s in found)


def test_missing_sections_detected():
    partial = "## Executive Summary\nSome finding.\n## Recommendations\nDo something."
    score = score_report(partial, GROUND_TRUTH)
    assert "Timeline of Events" in score.sections_missing
    assert "Indicators of Compromise" in score.sections_missing
    assert score.section_score < 1.0


def test_persistence_flag():
    score = score_report(PERFECT_REPORT, GROUND_TRUTH)
    assert score.persistence_detected is True


def test_score_to_dict_structure():
    score = score_report(PERFECT_REPORT, GROUND_TRUTH)
    d = score.to_dict()
    assert "scores" in d
    assert "overall" in d["scores"]
    assert "ioc_f1" in d["scores"]
    assert "flags" in d