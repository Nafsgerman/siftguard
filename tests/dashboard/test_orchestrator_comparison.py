"""Tests for /api/orchestrator-comparison/{case_id} endpoint."""
import os
import pytest
from fastapi.testclient import TestClient

EXPECTED_LABELS = [
    "Native Loop (Sonnet)",
    "LangGraph (Sonnet)",
    "OpenAI FC (gpt-5.5)",
    "Gemini 3 Pro",
    "Claude Code (headless)",
]


def test_comparison_returns_five_rows():
    from siftguard.dashboard.app import app
    client = TestClient(app)
    r = client.get("/api/orchestrator-comparison/CASE-001")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 5
    labels = [row["label"] for row in data]
    assert labels == EXPECTED_LABELS


def test_all_rows_are_real():
    from siftguard.dashboard.app import app
    client = TestClient(app)
    data = client.get("/api/orchestrator-comparison/CASE-001").json()
    assert all(row["real"] is True for row in data)


def test_comparison_404_missing_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / "audit", exist_ok=True)
    from siftguard.dashboard.app import app
    client = TestClient(app)
    r = client.get("/api/orchestrator-comparison/NONEXISTENT")
    assert r.status_code == 404


def test_wall_time_present_for_all_rows():
    from siftguard.dashboard.app import app
    client = TestClient(app)
    data = client.get("/api/orchestrator-comparison/CASE-001").json()
    for row in data:
        assert "wall_ms" in row
