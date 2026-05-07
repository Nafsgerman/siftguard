"""Smoke tests for migration 002 — run_id column."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.migrate import column_exists, ensure_migrations_table

LEGACY_SCHEMA = """
CREATE TABLE auditentry (
    id INTEGER NOT NULL,
    case_id VARCHAR NOT NULL,
    timestamp DATETIME NOT NULL,
    tool_name VARCHAR NOT NULL,
    tool_version VARCHAR NOT NULL,
    args_json VARCHAR NOT NULL,
    args_sha256 VARCHAR NOT NULL,
    outcome VARCHAR NOT NULL,
    output_sha256 VARCHAR NOT NULL,
    output_excerpt VARCHAR NOT NULL,
    duration_ms INTEGER NOT NULL,
    agent_iteration INTEGER,
    hypothesis_id VARCHAR,
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd REAL,
    confidence_score REAL,
    correction_event TEXT,
    PRIMARY KEY (id)
)
"""


@pytest.fixture
def post_001_db(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.execute(LEGACY_SCHEMA)
    conn.commit()
    yield conn
    conn.close()


def _apply_002(conn: sqlite3.Connection) -> None:
    ensure_migrations_table(conn)
    if not column_exists(conn, "auditentry", "run_id"):
        conn.execute("ALTER TABLE auditentry ADD COLUMN run_id TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_auditentry_run_id ON auditentry (run_id)"
        )
        conn.commit()


def test_run_id_column_added(post_001_db):
    _apply_002(post_001_db)
    assert column_exists(post_001_db, "auditentry", "run_id")


def test_migration_002_idempotent(post_001_db):
    _apply_002(post_001_db)
    _apply_002(post_001_db)
    assert column_exists(post_001_db, "auditentry", "run_id")


def test_existing_rows_get_null_run_id(post_001_db):
    post_001_db.execute(
        "INSERT INTO auditentry "
        "(case_id, timestamp, tool_name, tool_version, args_json, "
        " args_sha256, outcome, output_sha256, output_excerpt, duration_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("CASE-1", "2026-05-06 10:00:00", "vol_pslist", "v3",
         "{}", "abc", "ok", "def", "summary", 100),
    )
    post_001_db.commit()
    _apply_002(post_001_db)
    cur = post_001_db.execute("SELECT run_id FROM auditentry WHERE case_id='CASE-1'")
    row = cur.fetchone()
    assert row[0] is None


def test_new_rows_accept_run_id(post_001_db):
    _apply_002(post_001_db)
    post_001_db.execute(
        "INSERT INTO auditentry "
        "(case_id, timestamp, tool_name, tool_version, args_json, "
        " args_sha256, outcome, output_sha256, output_excerpt, duration_ms, run_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("CASE-2", "2026-05-06 10:00:00", "vol_pslist", "v3",
         "{}", "abc", "ok", "def", "summary", 100, "run-abc-123"),
    )
    post_001_db.commit()
    cur = post_001_db.execute("SELECT run_id FROM auditentry WHERE case_id='CASE-2'")
    assert cur.fetchone()[0] == "run-abc-123"