"""Tests for seed_spoliation_receipts and SnapshotWriter.emit_blocked_mutation."""
import sqlite3
import tempfile
from pathlib import Path

import pytest

from siftguard.agent.instrumentation import SnapshotWriter


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_audit.db"
    # Bootstrap the blocked_mutation table (mirrors the Alembic migration schema)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blocked_mutation (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id    TEXT    NOT NULL UNIQUE,
                case_id       TEXT    NOT NULL,
                attempted_action TEXT NOT NULL,
                reason        TEXT    NOT NULL,
                actor         TEXT    NOT NULL DEFAULT 'siftguard-agent',
                timestamp     TEXT    NOT NULL
            )
            """
        )
    return db_path


def test_emit_blocked_mutation_returns_uuid(tmp_db: Path) -> None:
    writer = SnapshotWriter(db_path=str(tmp_db))
    rid = writer.emit_blocked_mutation(
        case_id="TEST-001",
        attempted_action="DELETE FROM iteration_snapshot WHERE id=1",
        reason="Append-only violation",
    )
    assert len(rid) == 36  # UUID4 canonical form
    assert rid.count("-") == 4


def test_emit_blocked_mutation_persists_row(tmp_db: Path) -> None:
    writer = SnapshotWriter(db_path=str(tmp_db))
    rid = writer.emit_blocked_mutation(
        case_id="TEST-001",
        attempted_action="UPDATE hypothesis_event SET event_type='x' WHERE id=1",
        reason="UPDATE rejected",
        actor="test-actor",
    )
    with sqlite3.connect(str(tmp_db)) as conn:
        row = conn.execute(
            "SELECT case_id, attempted_action, reason, actor FROM blocked_mutation WHERE receipt_id=?",
            (rid,),
        ).fetchone()
    assert row is not None
    assert row[0] == "TEST-001"
    assert row[2] == "UPDATE rejected"
    assert row[3] == "test-actor"


def test_three_seed_receipts_written(tmp_db: Path) -> None:
    """Mirrors what seed_spoliation_receipts.py does — 3 receipts, all unique."""
    from scripts.seed_spoliation_receipts import RECEIPTS

    writer = SnapshotWriter(db_path=str(tmp_db))
    ids = [
        writer.emit_blocked_mutation(
            case_id=r["case_id"],
            attempted_action=r["attempted_action"],
            reason=r["reason"],
            actor=r["actor"],
        )
        for r in RECEIPTS
    ]
    assert len(ids) == 3
    assert len(set(ids)) == 3  # all unique UUIDs

    with sqlite3.connect(str(tmp_db)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM blocked_mutation").fetchone()[0]
    assert count == 3


def test_emit_blocked_mutation_default_actor(tmp_db: Path) -> None:
    writer = SnapshotWriter(db_path=str(tmp_db))
    rid = writer.emit_blocked_mutation(
        case_id="TEST-001",
        attempted_action="DROP TABLE blocked_mutation",
        reason="Schema mutation rejected",
    )
    with sqlite3.connect(str(tmp_db)) as conn:
        actor = conn.execute(
            "SELECT actor FROM blocked_mutation WHERE receipt_id=?", (rid,)
        ).fetchone()[0]
    assert actor == "siftguard-agent"