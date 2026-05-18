"""Unit tests for ClaudeCodeAdapter. Mocks subprocess — no real `claude` CLI required."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from siftguard.eval.orchestrators.claude_code_adapter import (
    REPORT_BLOCK_RE,
    ClaudeCodeAdapter,
)


@pytest.fixture
def fake_project(tmp_path: Path) -> Path:
    (tmp_path / "CLAUDE.md").write_text("# stub")
    (tmp_path / ".mcp.json").write_text("{}")
    return tmp_path


def _envelope(result_text: str, num_turns: int = 14) -> str:
    return json.dumps({"result": result_text, "num_turns": num_turns, "total_cost_usd": 0.12})


def test_parses_report_block(fake_project: Path) -> None:
    report = {
        "case_id": "TEST-001",
        "verdict": "malicious",
        "confidence": 0.92,
        "summary": "x",
        "confirmed_iocs": [],
        "suspicious_indicators": [],
        "sections": {},
        "tool_calls_made": 14,
        "stopped_early": False,
    }
    final = f"some prose\n```siftguard-report\n{json.dumps(report)}\n```\ntrailing"

    mock_proc = MagicMock(returncode=0, stdout=_envelope(final), stderr="")
    with patch("subprocess.run", return_value=mock_proc):
        result = ClaudeCodeAdapter(cwd=fake_project).run("TEST-001", "go")

    assert result.success
    assert result.report["verdict"] == "malicious"
    assert result.tool_calls == 14


def test_missing_report_block_marks_failure(fake_project: Path) -> None:
    mock_proc = MagicMock(returncode=0, stdout=_envelope("agent wandered off"), stderr="")
    with patch("subprocess.run", return_value=mock_proc):
        result = ClaudeCodeAdapter(cwd=fake_project).run("TEST-001", "go")

    assert not result.success
    assert "no siftguard-report block" in result.error


def test_timeout_returns_structured_failure(fake_project: Path) -> None:
    exc = subprocess.TimeoutExpired(cmd=["claude"], timeout=5, output=b"", stderr=b"")
    with patch("subprocess.run", side_effect=exc):
        result = ClaudeCodeAdapter(cwd=fake_project, timeout_s=5).run("TEST-001", "go")

    assert not result.success
    assert "timeout" in result.error


def test_nonzero_exit_marks_failure(fake_project: Path) -> None:
    mock_proc = MagicMock(returncode=2, stdout="", stderr="boom")
    with patch("subprocess.run", return_value=mock_proc):
        result = ClaudeCodeAdapter(cwd=fake_project).run("TEST-001", "go")

    assert not result.success
    assert "exit=2" in result.error


def test_missing_claudemd_raises(tmp_path: Path) -> None:
    (tmp_path / ".mcp.json").write_text("{}")
    with pytest.raises(FileNotFoundError, match="CLAUDE.md"):
        ClaudeCodeAdapter(cwd=tmp_path).run("TEST-001", "go")


def test_regex_matches_multiline_json() -> None:
    sample = '```siftguard-report\n{\n  "verdict": "clean"\n}\n```'
    m = REPORT_BLOCK_RE.search(sample)
    assert m and json.loads(m.group("json"))["verdict"] == "clean"
