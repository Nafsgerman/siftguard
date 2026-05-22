"""Unit tests for system_prompt_gate — behavioral gate for self-correction ablation."""

from __future__ import annotations

import pytest

from siftguard.agent.system_prompt_gate import (
    SELF_CORRECTION_OFF_PREFIX,
    build_system_prompt_prefix,
)


def test_on_returns_empty_gate_no_preamble():
    result = build_system_prompt_prefix(self_correction=True)
    assert result == ""


def test_on_returns_preamble_only():
    result = build_system_prompt_prefix(self_correction=True, tool_preamble="TOOLS: ...")
    assert result == "TOOLS: ..."


def test_off_returns_gate_prefix():
    result = build_system_prompt_prefix(self_correction=False)
    assert result == SELF_CORRECTION_OFF_PREFIX
    assert "SELF-CORRECTION DISABLED" in result
    assert "do not retry" in result
    assert "do not substitute" in result
    assert "reduced confidence" in result


def test_off_gate_prepends_before_preamble():
    preamble = "TOOLS: vol, regripper"
    result = build_system_prompt_prefix(self_correction=False, tool_preamble=preamble)
    assert result.startswith(SELF_CORRECTION_OFF_PREFIX)
    assert result.endswith(preamble)
    assert result == SELF_CORRECTION_OFF_PREFIX + preamble


def test_off_gate_ends_with_double_newline():
    result = build_system_prompt_prefix(self_correction=False)
    assert result.endswith("\n\n")


def test_constant_is_non_ascii_safe():
    SELF_CORRECTION_OFF_PREFIX.encode("utf-8")  # must not raise


def test_on_is_falsy_when_no_preamble():
    assert not build_system_prompt_prefix(self_correction=True)


def test_off_is_truthy():
    assert build_system_prompt_prefix(self_correction=False)
