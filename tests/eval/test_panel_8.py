from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from siftguard.eval.verifier_models import VerificationResult, VerificationStatus, VerificationMethod
from siftguard.eval.analytics.panel_8_verification import get_verification_breakdown, render_panel_8


def _finding(status: VerificationStatus, method: VerificationMethod) -> MagicMock:
    f = MagicMock()
    f.verification = VerificationResult(
        finding_id="F-test",
        status=status,
        method=method,
        confidence=0.9,
    )
    return f


def _trace(findings: list) -> MagicMock:
    t = MagicMock()
    t.findings = findings
    return t


def test_empty_traces_returns_zero_rates():
    bd = get_verification_breakdown([])
    assert bd["total"] == 0
    assert bd["hallucination_rate"] == 0.0
    assert bd["verified_rate"] == 0.0


def test_no_verification_field_skipped():
    f = MagicMock(spec=[])  # no .verification attribute
    trace = _trace([f])
    bd = get_verification_breakdown([trace])
    assert bd["total"] == 0


def test_all_verified():
    findings = [_finding(VerificationStatus.VERIFIED, VerificationMethod.SUBSTRING_MATCH) for _ in range(5)]
    bd = get_verification_breakdown([_trace(findings)])
    assert bd["total"] == 5
    assert bd["verified"] == 5
    assert bd["refuted"] == 0
    assert bd["hallucination_rate"] == 0.0
    assert bd["verified_rate"] == 1.0


def test_all_refuted():
    findings = [_finding(VerificationStatus.REFUTED, VerificationMethod.TOOL_RERUN) for _ in range(3)]
    bd = get_verification_breakdown([_trace(findings)])
    assert bd["hallucination_rate"] == 1.0
    assert bd["tool_rerun_count"] == 3


def test_mixed_findings():
    findings = [
        _finding(VerificationStatus.VERIFIED, VerificationMethod.SUBSTRING_MATCH),
        _finding(VerificationStatus.VERIFIED, VerificationMethod.SUBSTRING_MATCH),
        _finding(VerificationStatus.REFUTED, VerificationMethod.SUBSTRING_MATCH),
        _finding(VerificationStatus.UNVERIFIABLE, VerificationMethod.UNVERIFIABLE),
    ]
    bd = get_verification_breakdown([_trace(findings)])
    assert bd["total"] == 4
    assert bd["verified"] == 2
    assert bd["refuted"] == 1
    assert bd["unverifiable"] == 1
    assert abs(bd["hallucination_rate"] - 0.25) < 0.001
    assert bd["substring_count"] == 3


def test_render_panel_8_no_data():
    result = render_panel_8([])
    assert result["status"] == "no_data"
    assert "no_data" in result["status"]


def test_render_panel_8_ok():
    findings = [
        _finding(VerificationStatus.VERIFIED, VerificationMethod.SUBSTRING_MATCH),
        _finding(VerificationStatus.REFUTED, VerificationMethod.TOOL_RERUN),
    ]
    result = render_panel_8([_trace(findings)])
    assert result["status"] == "ok"
    assert "50.0%" in result["summary"]
    assert "Hallucination Rate" in result["summary"]


def test_method_breakdown_counts():
    findings = [
        _finding(VerificationStatus.VERIFIED, VerificationMethod.SUBSTRING_MATCH),
        _finding(VerificationStatus.VERIFIED, VerificationMethod.TOOL_RERUN),
        _finding(VerificationStatus.REFUTED, VerificationMethod.TOOL_RERUN),
    ]
    bd = get_verification_breakdown([_trace(findings)])
    assert bd["substring_count"] == 1
    assert bd["tool_rerun_count"] == 2
