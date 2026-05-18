"""Benchmark fixture assertion — zero API cost.

Structure: data["panel_7"]["data"][agent_label]["mean"] -> float F1
No live API calls. The committed JSON IS the fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ANALYSIS_PATH = (
    Path(__file__).resolve().parents[2] / "experiments" / "analysis" / "TEST-001" / "data.json"
)

MIN_AGENT_COUNT = 3
F1_FLOOR = 0.5


@pytest.fixture(scope="module")
def analysis_data() -> dict:
    assert ANALYSIS_PATH.exists(), f"Missing fixture: {ANALYSIS_PATH}"
    return json.loads(ANALYSIS_PATH.read_text())


def test_fixture_is_valid_json(analysis_data: dict) -> None:
    assert isinstance(analysis_data, dict)


def test_panel_7_key_present(analysis_data: dict) -> None:
    assert "panel_7" in analysis_data
    assert "data" in analysis_data["panel_7"]


def test_agent_entries_present(analysis_data: dict) -> None:
    agents = analysis_data["panel_7"]["data"]
    assert len(agents) >= MIN_AGENT_COUNT, f"Only {len(agents)} agents: {list(agents.keys())}"


def test_all_agents_have_mean_f1(analysis_data: dict) -> None:
    agents = analysis_data["panel_7"]["data"]
    for label, block in agents.items():
        mean = block.get("mean")
        assert mean is not None, f"Agent '{label}' missing 'mean'"
        assert 0.0 <= float(mean) <= 1.0, f"Agent '{label}' mean={mean} out of range"


def test_best_agent_f1_above_floor(analysis_data: dict) -> None:
    agents = analysis_data["panel_7"]["data"]
    scores = [float(b["mean"]) for b in agents.values() if b.get("mean") is not None]
    assert scores, "No mean F1 scores found"
    assert max(scores) > F1_FLOOR, f"Best F1={max(scores):.3f} below {F1_FLOOR} floor"


def test_each_agent_has_runs(analysis_data: dict) -> None:
    agents = analysis_data["panel_7"]["data"]
    for label, block in agents.items():
        assert len(block.get("runs", [])) >= 1, f"Agent '{label}' has no runs"
