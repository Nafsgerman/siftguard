"""Tests for v2 structured output schema — ADR-003."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from siftguard.agent.output_schema import (
    AgentOutput,
    FindingOutput,
)


def _finding(fid: str = "f1", confidence: float = 0.85) -> dict:
    return {
        "id": fid,
        "type": "ip",
        "value": "172.16.4.10",
        "confidence": confidence,
        "evidence_excerpt": "172.16.4.10:8080 CLOSE_WAIT",
        "reasoning": "C2 beacon confirmed by netscan.",
    }


def _base_output(**kwargs) -> dict:
    base = {
        "iteration_summary": "Initial recon complete.",
        "findings": [],
        "hypotheses": [],
        "next_action": {
            "decision": "continue",
            "tool_to_call": "vol_netscan",
            "rationale": "Check network connections.",
        },
        "verdict": None,
    }
    base.update(kwargs)
    return base


# ── Finding validation ────────────────────────────────────────────────────────


def test_finding_rejects_below_floor():
    with pytest.raises(ValidationError, match="0.30 reporting floor"):
        FindingOutput(**{**_finding(), "confidence": 0.29})


def test_finding_accepts_at_floor():
    f = FindingOutput(**{**_finding(), "confidence": 0.30})
    assert f.confidence == 0.30


def test_finding_rejects_short_excerpt():
    with pytest.raises(ValidationError, match="too short"):
        FindingOutput(**{**_finding(), "evidence_excerpt": "short"})


def test_finding_rejects_long_excerpt():
    with pytest.raises(ValidationError, match="too long"):
        FindingOutput(**{**_finding(), "evidence_excerpt": "x" * 201})


# ── Verdict aggregation rule ──────────────────────────────────────────────────


def test_verdict_confidence_exceeds_min_finding_rejected():
    data = _base_output(
        findings=[_finding("f1", confidence=0.65)],
        next_action={
            "decision": "verdict",
            "tool_to_call": None,
            "rationale": "Sufficient evidence.",
        },
        verdict={
            "claim": "CONFIRMED COMPROMISE",
            "confidence": 0.95,
            "supporting_finding_ids": ["f1"],
            "reasoning": "C2 beacon confirmed.",
            "mitre_techniques": ["T1071"],
        },
    )
    with pytest.raises(ValidationError, match="exceeds minimum supporting finding"):
        AgentOutput.model_validate(data)


def test_verdict_confidence_equals_min_finding_accepted():
    data = _base_output(
        findings=[_finding("f1", confidence=0.75)],
        next_action={
            "decision": "verdict",
            "tool_to_call": None,
            "rationale": "Sufficient evidence.",
        },
        verdict={
            "claim": "CONFIRMED COMPROMISE",
            "confidence": 0.75,
            "supporting_finding_ids": ["f1"],
            "reasoning": "C2 beacon confirmed.",
            "mitre_techniques": ["T1071"],
        },
    )
    output = AgentOutput.model_validate(data)
    assert output.verdict.confidence == 0.75


def test_verdict_below_min_finding_accepted():
    data = _base_output(
        findings=[_finding("f1", confidence=0.80)],
        next_action={
            "decision": "verdict",
            "tool_to_call": None,
            "rationale": "Sufficient evidence.",
        },
        verdict={
            "claim": "CONFIRMED COMPROMISE",
            "confidence": 0.70,
            "supporting_finding_ids": ["f1"],
            "reasoning": "Conservative verdict.",
            "mitre_techniques": [],
        },
    )
    output = AgentOutput.model_validate(data)
    assert output.verdict.confidence == 0.70


def test_verdict_unknown_finding_id_rejected():
    data = _base_output(
        findings=[_finding("f1", confidence=0.80)],
        next_action={"decision": "verdict", "tool_to_call": None, "rationale": "Done."},
        verdict={
            "claim": "CONFIRMED",
            "confidence": 0.75,
            "supporting_finding_ids": ["nonexistent"],
            "reasoning": "...",
            "mitre_techniques": [],
        },
    )
    with pytest.raises(ValidationError, match="not present"):
        AgentOutput.model_validate(data)


# ── Correction event ──────────────────────────────────────────────────────────


def test_valid_correction_events():
    for event in [
        "tool_failure_recovery",
        "hypothesis_revision",
        "data_conflict",
        "gap_detection",
    ]:
        data = _base_output(correction_event=event)
        out = AgentOutput.model_validate(data)
        assert out.correction_event == event


def test_invalid_correction_event_rejected():
    data = _base_output(correction_event="made_up_event")
    with pytest.raises(ValidationError):
        AgentOutput.model_validate(data)


def test_null_correction_event_accepted():
    data = _base_output(correction_event=None)
    out = AgentOutput.model_validate(data)
    assert out.correction_event is None


# ── Output validator ──────────────────────────────────────────────────────────


def test_extract_json_block_found():
    from siftguard.agent.output_validator import extract_json_block

    text = 'Some reasoning...\n```json\n{"key": "val"}\n```'
    result = extract_json_block(text)
    assert result == '{"key": "val"}'


def test_extract_json_block_not_found():
    from siftguard.agent.output_validator import extract_json_block

    assert extract_json_block("no json block here") is None


def test_parse_agent_output_missing_block():
    from siftguard.agent.output_validator import parse_agent_output

    out, err = parse_agent_output("Just some text, no JSON.")
    assert out is None
    assert "```json" in err


def test_parse_agent_output_invalid_json():
    from siftguard.agent.output_validator import parse_agent_output

    out, err = parse_agent_output("```json\n{bad json}\n```")
    assert out is None
    assert "parse error" in err.lower()


def test_parse_agent_output_valid():
    import json

    from siftguard.agent.output_validator import parse_agent_output

    payload = _base_output(findings=[_finding()])
    text = f"Some reasoning.\n```json\n{json.dumps(payload)}\n```"
    out, err = parse_agent_output(text)
    assert out is not None
    assert err is None
    assert len(out.findings) == 1


def test_prompt_loading():
    from siftguard.agent.prompts import available_versions, load_prompt

    for version in available_versions():
        text = load_prompt(version)
        assert len(text) > 100


def test_prompt_v2_contains_calibration_anchors():
    from siftguard.agent.prompts import load_prompt

    v2 = load_prompt("v2")
    assert "0.95" in v2
    assert "0.70" in v2
    assert "0.50" in v2
    assert "0.30" in v2


def test_prompt_v2_contains_json_schema_marker():
    from siftguard.agent.prompts import load_prompt

    v2 = load_prompt("v2")
    assert "next_action" in v2
    assert "evidence_excerpt" in v2
    assert "correction_event" in v2


def test_prompt_invalid_version_raises():
    from siftguard.agent.prompts import load_prompt

    with pytest.raises(ValueError, match="Unknown prompt version"):
        load_prompt("v99")
