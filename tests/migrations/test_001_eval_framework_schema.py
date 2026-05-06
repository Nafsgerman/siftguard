"""Smoke tests for migration 001 — empirical evaluation framework schema."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# Allow `python -m pytest` from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.migrate import (
    apply_migration_001,
    column_exists,
    ensure_migrations_table,
    table_exists,
    verify_migration_001,
)

# Schema of v1.0.0-hackathon-baseline auditentry table — frozen.
LEGACY_AUDITENTRY_SCHEMA = """
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
    PRIMARY KEY (id)
)
"""


@pytest.fixture
def legacy_db(tmp_path):
    """A DB matching v1.0.0 schema — pre-migration state."""
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute(LEGACY_AUDITENTRY_SCHEMA)
    conn.commit()
    yield conn
    conn.close()


def test_migration_adds_all_auditentry_columns(legacy_db):
    ensure_migrations_table(legacy_db)
    apply_migration_001(legacy_db)
    for col in ["tokens_in", "tokens_out", "cost_usd",
                "confidence_score", "correction_event"]:
        assert column_exists(legacy_db, "auditentry", col), f"{col} missing"


def test_migration_creates_all_new_tables(legacy_db):
    ensure_migrations_table(legacy_db)
    apply_migration_001(legacy_db)
    for t in ["iteration_snapshot", "hypothesis_event",
              "experiment_run", "schema_migrations"]:
        assert table_exists(legacy_db, t), f"table {t} missing"


def test_migration_is_idempotent(legacy_db):
    """Running twice must not raise (no duplicate-column error)."""
    ensure_migrations_table(legacy_db)
    apply_migration_001(legacy_db)
    apply_migration_001(legacy_db)


def test_legacy_writes_still_work(legacy_db):
    """Existing audit/log.py write API must keep working post-migration."""
    ensure_migrations_table(legacy_db)
    apply_migration_001(legacy_db)
    legacy_db.execute(
        "INSERT INTO auditentry "
        "(case_id, timestamp, tool_name, tool_version, "
        " args_json, args_sha256, outcome, output_sha256, "
        " output_excerpt, duration_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("CASE-TEST", "2026-05-06 14:00:00", "vol_pslist", "v3",
         "{}", "abc", "ok", "def", "summary", 100),
    )
    legacy_db.commit()
    cur = legacy_db.execute("SELECT case_id, tool_name FROM auditentry")
    row = cur.fetchone()
    assert row == ("CASE-TEST", "vol_pslist")


def test_new_columns_accept_values(legacy_db):
    ensure_migrations_table(legacy_db)
    apply_migration_001(legacy_db)
    legacy_db.execute(
        "INSERT INTO auditentry "
        "(case_id, timestamp, tool_name, tool_version, "
        " args_json, args_sha256, outcome, output_sha256, "
        " output_excerpt, duration_ms, "
        " tokens_in, tokens_out, cost_usd, "
        " confidence_score, correction_event) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("CASE-TEST", "2026-05-06 14:00:00", "vol_pslist", "v3",
         "{}", "abc", "ok", "def", "summary", 100,
         1234, 567, 0.0042, 0.85, "tool_failure_recovery"),
    )
    legacy_db.commit()
    cur = legacy_db.execute(
        "SELECT tokens_in, tokens_out, cost_usd, confidence_score, correction_event "
        "FROM auditentry WHERE case_id=?", ("CASE-TEST",),
    )
    row = cur.fetchone()
    assert row == (1234, 567, 0.0042, 0.85, "tool_failure_recovery")


def test_hypothesis_event_constraint(legacy_db):
    ensure_migrations_table(legacy_db)
    apply_migration_001(legacy_db)
    with pytest.raises(sqlite3.IntegrityError):
        legacy_db.execute(
            "INSERT INTO hypothesis_event "
            "(run_id, case_id, iteration, event_type, hypothesis_id, content) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("run-1", "CASE-1", 0, "INVALID_TYPE", "h1", "test"),
        )


def test_iteration_snapshot_unique_constraint(legacy_db):
    """Same (run_id, iteration) cannot be inserted twice."""
    ensure_migrations_table(legacy_db)
    apply_migration_001(legacy_db)
    legacy_db.execute(
        "INSERT INTO iteration_snapshot "
        "(run_id, case_id, iteration, findings_json, iocs_json, hypotheses_json, wall_time_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("run-1", "CASE-1", 0, "[]", "[]", "[]", 1000),
    )
    legacy_db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        legacy_db.execute(
            "INSERT INTO iteration_snapshot "
            "(run_id, case_id, iteration, findings_json, iocs_json, hypotheses_json, wall_time_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-1", "CASE-1", 0, "[]", "[]", "[]", 2000),
        )


def test_verify_passes_after_migration(legacy_db):
    ensure_migrations_table(legacy_db)
    apply_migration_001(legacy_db)
    assert verify_migration_001(legacy_db)


def test_verify_fails_before_migration(legacy_db):
    ensure_migrations_table(legacy_db)
    assert not verify_migration_001(legacy_db)