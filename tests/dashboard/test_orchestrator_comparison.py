"""Tests for /api/orchestrator-comparison/{case_id} endpoint."""
import json
import os
import shutil
import sqlite3

import pytest
from fastapi.testclient import TestClient


def _make_db(path: str):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE experiment_run (
            run_id TEXT PRIMARY KEY, case_id TEXT, agent_id TEXT,
            config_json TEXT, final_score REAL, total_cost_usd REAL,
            completed_iterations INTEGER, terminated_reason TEXT,
            total_tokens_in INTEGER DEFAULT 0, total_tokens_out INTEGER DEFAULT 0,
            started_at TEXT, completed_at TEXT
        );
        INSERT INTO experiment_run VALUES
            ('run-native-1','CASE-001','siftguard-native','{"orchestrator":"native"}',
             0.909,0.012,5,'verdict_reached',1000,500,
             '2026-05-10T10:00:00.000000+00:00','2026-05-10T10:00:50.000000+00:00'),
            ('run-lg-1','CASE-001','siftguard-langgraph','{"orchestrator":"langgraph"}',
             0.909,0.013,5,'verdict_reached',1000,500,
             '2026-05-10T10:01:00.000000+00:00','2026-05-10T10:02:31.000000+00:00');
    """)
    conn.commit()
    conn.close()


def test_comparison_returns_three_rows(tmp_path, monkeypatch):
    db = tmp_path / "CASE-001.db"
    _make_db(str(db))
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / "audit", exist_ok=True)
    shutil.copy(str(db), str(tmp_path / "audit" / "CASE-001.db"))
    from siftguard.dashboard.app import app
    client = TestClient(app)
    r = client.get("/api/orchestrator-comparison/CASE-001")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert data[0]["label"] == "Native Loop"
    assert data[0]["real"] is True
    assert data[0]["f1"] is None or data[0]["f1"] == 0.909
    assert data[1]["label"] == "LangGraph Adapter"
    assert data[1]["real"] is True
    assert data[2]["label"] == "OpenAI FC (Adapter in Progress)"
    assert data[2]["real"] is False
    assert data[2]["f1"] is None


def test_comparison_404_missing_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / "audit", exist_ok=True)
    from siftguard.dashboard.app import app
    client = TestClient(app)
    r = client.get("/api/orchestrator-comparison/NONEXISTENT")
    assert r.status_code == 404


def test_wall_time_computed(tmp_path, monkeypatch):
    db = tmp_path / "CASE-001.db"
    _make_db(str(db))
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / "audit", exist_ok=True)
    shutil.copy(str(db), str(tmp_path / "audit" / "CASE-001.db"))
    from siftguard.dashboard.app import app
    client = TestClient(app)
    data = client.get("/api/orchestrator-comparison/CASE-001").json()
    assert data[0]["wall_ms"] == 50000   # native: 50s
    assert data[1]["wall_ms"] == 91000   # langgraph: 91s
