"""Tests for CLI flag parsing and agent normalization."""
from __future__ import annotations

import pytest

from siftguard.eval.run_experiment import normalize_agent_id, _parse_args


def test_normalize_short_aliases():
    assert normalize_agent_id("langgraph") == "siftguard-langgraph"
    assert normalize_agent_id("openai-fc") == "siftguard-openai-fc"
    assert normalize_agent_id("gemini") == "siftguard-gemini"
    assert normalize_agent_id("claudecode") == "siftguard-claudecode"
    assert normalize_agent_id("native") == "siftguard-v2"


def test_normalize_canonical_passthrough():
    assert normalize_agent_id("siftguard-langgraph") == "siftguard-langgraph"


def test_normalize_unknown_raises():
    with pytest.raises(SystemExit):
        normalize_agent_id("not-a-real-agent")


def test_parse_args_agent_preferred():
    a = _parse_args(["--agent", "langgraph", "--case", "TEST-001"])
    assert a.agent_canonical == "siftguard-langgraph"
    assert a.gt_version == "1.1.0"


def test_parse_args_orchestrator_deprecated_alias():
    a = _parse_args(["--orchestrator", "gemini", "--case", "TEST-002"])
    assert a.agent_canonical == "siftguard-gemini"


def test_parse_args_requires_one_of(capsys):
    with pytest.raises(SystemExit):
        _parse_args(["--case", "TEST-001"])


def test_parse_args_gt_version_override():
    a = _parse_args(["--agent", "native", "--case", "TEST-001", "--gt-version", "1.0.0"])
    assert a.gt_version == "1.0.0"