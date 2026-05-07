"""Load experiment runs from results directory into Trace objects.

Reads result JSON files produced by experiments/run.py and attempts to
build Trace objects from the audit DB via TraceBuilder.
Falls back to a lightweight summary-only object when the DB is unavailable.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parents[4] / "experiments" / "results"
CASES_ROOT  = Path("/cases")


@dataclass
class RunSummary:
    """Lightweight run record loaded from result JSON."""
    config_name:   str
    case_id:       str
    status:        str
    report_path:   str | None
    wall_time:     float
    timestamp:     str
    config:        dict = field(default_factory=dict)
    run_id:        str | None = None
    final_score:   float | None = None
    total_cost_usd: float | None = None
    completed_iterations: int | None = None


def load_all_run_summaries() -> list[RunSummary]:
    """Load all result JSON files from experiments/results/."""
    summaries = []
    for result_file in sorted(RESULTS_DIR.rglob("result_*.json")):
        try:
            data = json.loads(result_file.read_text())
            config_path = (
                Path(__file__).resolve().parents[4]
                / "experiments" / "configs"
                / f"{data.get('config','')}.json"
            )
            config = {}
            if config_path.exists():
                config = json.loads(config_path.read_text())
            summaries.append(RunSummary(
                config_name=data.get("config", "unknown"),
                case_id=data.get("case_id", "unknown"),
                status=data.get("status", "unknown"),
                report_path=data.get("report"),
                wall_time=data.get("wall_time", 0.0),
                timestamp=data.get("timestamp", ""),
                config=config,
            ))
        except Exception:
            continue
    return summaries


def load_experiment_runs_from_db(db_path: str | Path) -> list[dict]:
    """Load experiment_run rows from audit DB."""
    runs = []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM experiment_run ORDER BY started_at"
        )
        for row in cur.fetchall():
            runs.append(dict(row))
        conn.close()
    except Exception:
        pass
    return runs


def load_iteration_snapshots(db_path: str | Path, run_id: str) -> list[dict]:
    """Load iteration_snapshot rows for a run."""
    snapshots = []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM iteration_snapshot WHERE run_id=? ORDER BY iteration",
            (run_id,),
        )
        for row in cur.fetchall():
            snapshots.append(dict(row))
        conn.close()
    except Exception:
        pass
    return snapshots


def load_audit_entries(db_path: str | Path, run_id: str) -> list[dict]:
    """Load auditentry rows for a run."""
    entries = []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM auditentry WHERE run_id=? ORDER BY id",
            (run_id,),
        )
        for row in cur.fetchall():
            entries.append(dict(row))
        conn.close()
    except Exception:
        pass
    return entries


def get_db_path(case_id: str) -> Path:
    if case_id == "TEST-001":
        return CASES_ROOT / "TEST-001" / "siftguard" / "audit" / "CASE-001.db"
    return CASES_ROOT / case_id / "siftguard" / "audit" / f"{case_id}.db"