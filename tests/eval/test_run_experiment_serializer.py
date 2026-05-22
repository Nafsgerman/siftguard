"""Tests for _write_raw_result: structured payload when AgentOutput is parsable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from siftguard.eval import run_experiment

VALID_AGENT_TEXT = '## Incident Report\n\n```json\n{"stub": true}\n```\n'


class _FakeParsed:
    """Stand-in for AgentOutput; only model_dump is exercised by the serializer."""

    def model_dump(self, mode: str = "python") -> dict:
        return {
            "iteration_summary": "stub",
            "correction_event": "tool_failure_recovery",
            "findings": [{"id": "f1", "type": "process"}],
            "next_action": {"decision": "verdict"},
        }


def _patch_parser(monkeypatch: pytest.MonkeyPatch, parsed: object | None, err: str | None) -> None:
    """Monkeypatch the parser inside the validator module (where the serializer imports it)."""
    monkeypatch.setattr(
        "siftguard.agent.output_validator.parse_agent_output",
        lambda _text: (parsed, err),
    )


def test_writes_structured_body_when_text_parses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run_experiment, "RESULTS_DIR", tmp_path)
    _patch_parser(monkeypatch, _FakeParsed(), None)

    out = run_experiment._write_raw_result(
        "siftguard-v2", "TEST-001", VALID_AGENT_TEXT, "20260522_120000"
    )
    body = json.loads(out.read_text())

    assert isinstance(body, dict)
    assert body["report_text"] == VALID_AGENT_TEXT
    assert body["parsed"]["correction_event"] == "tool_failure_recovery"
    assert body["parsed"]["findings"][0]["id"] == "f1"


def test_falls_back_to_raw_string_when_parse_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run_experiment, "RESULTS_DIR", tmp_path)
    _patch_parser(monkeypatch, None, "no json block")

    out = run_experiment._write_raw_result(
        "siftguard-v2", "TEST-001", "no json block here", "20260522_120001"
    )
    body = json.loads(out.read_text())
    assert body == "no json block here"


def test_dict_payload_passes_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_experiment, "RESULTS_DIR", tmp_path)
    out = run_experiment._write_raw_result(
        "siftguard-v2", "TEST-001", {"key": "val"}, "20260522_120002"
    )
    body = json.loads(out.read_text())
    assert body == {"key": "val"}


def test_payload_with_report_attr_uses_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Holder:
        report = VALID_AGENT_TEXT

    monkeypatch.setattr(run_experiment, "RESULTS_DIR", tmp_path)
    _patch_parser(monkeypatch, _FakeParsed(), None)

    out = run_experiment._write_raw_result("siftguard-v2", "TEST-001", Holder(), "20260522_120003")
    body = json.loads(out.read_text())

    assert isinstance(body, dict)
    assert body["parsed"]["correction_event"] == "tool_failure_recovery"
    assert body["report_text"] == VALID_AGENT_TEXT
