"""Tests for backfill_correction_event.py."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

SCHEMA = """
CREATE TABLE auditentry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    agent_iteration INTEGER NOT NULL,
    tool_name TEXT NOT NULL,
    outcome TEXT NOT NULL,
    correction_event TEXT
);
"""


@pytest.fixture
def db(tmp_path: Path) -> Path:
    p = tmp_path / "audit.db"
    conn = sqlite3.connect(p)
    conn.executescript(SCHEMA)
    rows = [
        ("R1", 0, "vol_pslist", "ok", None),
        ("R1", 1, "analyze_mft", "fail", None),
        ("R1", 1, "run_regripper", "fail", None),
        ("R1", 2, "run_regripper", "ok", None),
        ("R1", 2, "analyze_mft", "fail", None),
        ("R1", 3, "run_regripper", "ok", None),
        ("R1", 3, "run_regripper", "ok", None),
        ("R2", 0, "vol_pslist", "ok", None),
        ("R2", 1, "vol_netscan", "ok", None),
    ]
    conn.executemany(
        "INSERT INTO auditentry (run_id, agent_iteration, tool_name, outcome, correction_event) VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    return p


def _run(db: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/backfill_correction_event.py", "--db", str(db), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def test_dry_run_does_not_mutate(db: Path) -> None:
    _run(db)
    conn = sqlite3.connect(db)
    nulls = conn.execute(
        "SELECT COUNT(*) FROM auditentry WHERE correction_event IS NULL"
    ).fetchone()[0]
    assert nulls == 9


def test_apply_tags_recoveries_after_failure(db: Path) -> None:
    _run(db, "--apply")
    conn = sqlite3.connect(db)
    tagged = conn.execute(
        "SELECT id, agent_iteration FROM auditentry WHERE correction_event = 'tool_failure_recovery' ORDER BY id"
    ).fetchall()
    iters = sorted({r[1] for r in tagged})
    assert iters == [2, 3], (
        "only iter 2 and iter 3 should be tagged (recoveries after fails in iter 1 and 2)"
    )
    assert len(tagged) == 4


def test_apply_skips_runs_without_prior_failure(db: Path) -> None:
    _run(db, "--apply")
    conn = sqlite3.connect(db)
    r2_tagged = conn.execute(
        "SELECT COUNT(*) FROM auditentry WHERE run_id='R2' AND correction_event IS NOT NULL"
    ).fetchone()[0]
    assert r2_tagged == 0


def test_apply_is_idempotent(db: Path) -> None:
    _run(db, "--apply")
    _run(db, "--apply")
    conn = sqlite3.connect(db)
    tagged = conn.execute(
        "SELECT COUNT(*) FROM auditentry WHERE correction_event = 'tool_failure_recovery'"
    ).fetchone()[0]
    assert tagged == 4
