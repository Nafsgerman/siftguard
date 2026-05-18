"""Tests for Trace Pydantic model — ADR-002."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from siftguard.eval.trace import (
    SCHEMA_VERSION,
    ExperimentConfig,
    Finding,
    FindingType,
    Orchestrator,
    TerminatedReason,
    Trace,
    TraceMeta,
    Verdict,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _finding(**kwargs) -> Finding:
    defaults = {
        "type": FindingType.IP,
        "value": "172.16.4.10",
        "evidence_excerpt": "172.16.4.10:8080 CLOSE_WAIT",
        "first_seen_iteration": 0,
    }
    defaults.update(kwargs)
    return Finding(**defaults)


def _meta(**kwargs) -> TraceMeta:
    defaults = {
        "agent_id": "siftguard-v1",
        "case_id": "TEST-001",
        "started_at": datetime(2026, 5, 6, 9, 0, 0, tzinfo=UTC),
    }
    defaults.update(kwargs)
    return TraceMeta(**defaults)


def _config(**kwargs) -> ExperimentConfig:
    defaults = {"agent_id": "siftguard-v1", "model": "claude-sonnet-4-6"}
    defaults.update(kwargs)
    return ExperimentConfig(**defaults)


def _verdict(finding_ids: list[str]) -> Verdict:
    return Verdict(
        claim="CONFIRMED COMPROMISE — APT activity",
        confidence=0.95,
        supporting_finding_ids=finding_ids,
        reasoning="C2 beacon, backdoor processes, persistence mechanisms confirmed.",
        mitre_techniques=["T1071", "T1055"],
        terminated_reason=TerminatedReason.VERDICT_REACHED,
    )


def _minimal_trace(**kwargs) -> Trace:
    return Trace(meta=_meta(), config=_config(), **kwargs)


# ── Finding validation ─────────────────────────────────────────────────────────


def test_finding_valid():
    f = _finding()
    assert f.value == "172.16.4.10"
    assert f.type == FindingType.IP


def test_finding_rejects_short_excerpt():
    with pytest.raises(ValidationError, match="too short"):
        _finding(evidence_excerpt="x" * 9)


def test_finding_rejects_long_excerpt():
    with pytest.raises(ValidationError, match="too long"):
        _finding(evidence_excerpt="x" * 201)


def test_finding_confidence_range():
    _finding(confidence=0.0)
    _finding(confidence=1.0)
    _finding(confidence=None)
    with pytest.raises(ValidationError):
        _finding(confidence=1.1)
    with pytest.raises(ValidationError):
        _finding(confidence=-0.1)


def test_finding_none_confidence_allowed():
    """ADR-002 Q1: honest absence over synthetic data."""
    f = _finding(confidence=None)
    assert f.confidence is None


# ── Trace schema version ────────────────────────────────────────────────────────


def test_trace_rejects_unknown_schema_version():
    with pytest.raises(ValidationError, match="Unsupported schema_version"):
        meta = TraceMeta(
            agent_id="test",
            case_id="TEST-001",
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
            schema_version="9.9.9",
        )
        Trace(meta=meta, config=_config())


def test_trace_accepts_current_schema_version():
    t = _minimal_trace()
    assert t.meta.schema_version == SCHEMA_VERSION


# ── Verdict finding-id cross-reference ─────────────────────────────────────────


def test_verdict_rejects_unknown_finding_id():
    f = _finding()
    v = _verdict(["nonexistent-id"])
    with pytest.raises(ValidationError, match="not present in trace.findings"):
        Trace(meta=_meta(), config=_config(), findings=(f,), verdict=v)


def test_verdict_accepts_valid_finding_ids():
    f = _finding()
    v = _verdict([f.id])
    t = Trace(meta=_meta(), config=_config(), findings=(f,), verdict=v)
    assert t.verdict is not None


# ── Serialisation round-trip ────────────────────────────────────────────────────


def test_trace_json_round_trip():
    f = _finding()
    t = Trace(meta=_meta(), config=_config(), findings=(f,))
    json_str = t.to_json()
    t2 = Trace.from_json(json_str)
    assert t2.meta.case_id == t.meta.case_id
    assert len(t2.findings) == 1
    assert t2.findings[0].value == "172.16.4.10"


def test_trace_json_is_valid_json():
    t = _minimal_trace()
    parsed = json.loads(t.to_json())
    assert "meta" in parsed
    assert "config" in parsed


# ── Hash stability ──────────────────────────────────────────────────────────────


def test_trace_sha256_is_stable():
    f = _finding()
    t = Trace(meta=_meta(), config=_config(), findings=(f,))
    h1 = t.sha256()
    h2 = t.sha256()
    assert h1 == h2
    assert len(h1) == 64


def test_different_findings_produce_different_hashes():
    f1 = _finding(value="172.16.4.10")
    f2 = _finding(value="10.0.0.1")
    t1 = Trace(meta=_meta(), config=_config(), findings=(f1,))
    t2 = Trace(meta=_meta(), config=_config(), findings=(f2,))
    assert t1.sha256() != t2.sha256()


# ── Immutability ────────────────────────────────────────────────────────────────


def test_trace_is_immutable():
    t = _minimal_trace()
    with pytest.raises(Exception):
        t.meta = _meta(case_id="OTHER")


# ── ioc_findings property ───────────────────────────────────────────────────────


def test_ioc_findings_filters_correctly():
    f_ip = _finding(type=FindingType.IP)
    f_file = _finding(
        type=FindingType.FILE,
        value="malware.exe",
        evidence_excerpt="malware.exe found in temp directory",
    )
    t = Trace(meta=_meta(), config=_config(), findings=(f_ip, f_file))
    iocs = t.ioc_findings
    assert len(iocs) == 1
    assert iocs[0].type == FindingType.IP


# ── ExperimentConfig ablation fields ────────────────────────────────────────────


def test_config_defaults():
    c = _config()
    assert c.self_correction is True
    assert c.max_iterations == 15
    assert c.orchestrator == Orchestrator.SIFTGUARD_NATIVE


def test_config_ablation_flags():
    c = ExperimentConfig(
        agent_id="test",
        model="claude-sonnet-4-6",
        self_correction=False,
        correlation=False,
        max_iterations=1,
    )
    assert c.self_correction is False
    assert c.max_iterations == 1
