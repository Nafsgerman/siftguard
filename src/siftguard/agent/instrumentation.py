"""Instrumentation helpers for the v2 agent loop.

All writes are best-effort: failures are logged but never abort the agent loop.
Principle: investigation > telemetry.

ADR: docs/adr/ADR-003-loop-instrumentation.md
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# ── Token cost table ───────────────────────────────────────────────────────────
# Prices in USD per token. Update when pricing changes.
_COST_PER_TOKEN_IN: dict[str, float] = {
    "claude-sonnet-4-6": 3.00 / 1_000_000,
    "claude-opus-4-20250514": 15.00 / 1_000_000,
    "claude-haiku-4-20251001": 0.80 / 1_000_000,
    "gpt-4o": 2.50 / 1_000_000,
    "gpt-4o-mini": 0.15 / 1_000_000,
    "gemini-2.5-pro": 1.25 / 1_000_000,
}
_COST_PER_TOKEN_OUT: dict[str, float] = {
    "claude-sonnet-4-6": 15.00 / 1_000_000,
    "claude-opus-4-20250514": 75.00 / 1_000_000,
    "claude-haiku-4-20251001": 4.00 / 1_000_000,
    "gpt-4o": 10.00 / 1_000_000,
    "gpt-4o-mini": 0.60 / 1_000_000,
    "gemini-2.5-pro": 5.00 / 1_000_000,
}
_FALLBACK_COST_IN = 3.00 / 1_000_000
_FALLBACK_COST_OUT = 15.00 / 1_000_000


def token_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Return USD cost for a single API call."""
    rate_in = _COST_PER_TOKEN_IN.get(model, _FALLBACK_COST_IN)
    rate_out = _COST_PER_TOKEN_OUT.get(model, _FALLBACK_COST_OUT)
    return round(tokens_in * rate_in + tokens_out * rate_out, 8)


# ── Hypothesis tracker ─────────────────────────────────────────────────────────


def _jaccard(a: str, b: str) -> float:
    """Token-set Jaccard similarity."""
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class HypothesisTracker:
    """
    Tracks hypothesis belief evolution across iterations.
    Emits (hypothesis_id, event_type, content, confidence) tuples.
    """

    def __init__(self) -> None:
        self._prior: dict[str, dict] = {}

    def diff(
        self,
        current_hypotheses: list[dict],
    ) -> list[dict]:
        """
        Compare current hypotheses against prior state.
        Returns list of hypothesis event dicts ready for SnapshotWriter.
        """
        events = []
        current_ids = set()

        for hyp in current_hypotheses:
            hid = hyp.get("hypothesis_id", "")
            current_ids.add(hid)
            content = hyp.get("content", "")
            confidence = hyp.get("confidence", 0.0)
            event_type = hyp.get("event_type", "")

            if hid not in self._prior:
                events.append(
                    {
                        "hypothesis_id": hid,
                        "event_type": "formed",
                        "content": content,
                        "confidence": confidence,
                    }
                )
            else:
                prior_content = self._prior[hid].get("content", "")
                similarity = _jaccard(prior_content, content)
                if event_type == "abandoned":
                    events.append(
                        {
                            "hypothesis_id": hid,
                            "event_type": "abandoned",
                            "content": content,
                            "confidence": confidence,
                        }
                    )
                elif event_type == "confirmed":
                    events.append(
                        {
                            "hypothesis_id": hid,
                            "event_type": "confirmed",
                            "content": content,
                            "confidence": confidence,
                        }
                    )
                elif similarity < 0.7:
                    events.append(
                        {
                            "hypothesis_id": hid,
                            "event_type": "updated",
                            "content": content,
                            "confidence": confidence,
                        }
                    )

            self._prior[hid] = {"content": content, "confidence": confidence}

        return events


# ── Snapshot writer ────────────────────────────────────────────────────────────


class SnapshotWriter:
    """
    Writes instrumentation rows to the eval-framework tables.
    All writes are best-effort — failures logged, never raised.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        # ... existing init code ...

        # Guard: fail loud if schema not initialized
        import sqlite3 as _sqlite3

        try:
            _conn = _sqlite3.connect(db_path)
            _conn.execute("SELECT 1 FROM experiment_run LIMIT 1")
            _conn.close()
        except _sqlite3.OperationalError as exc:
            raise RuntimeError(
                f"SnapshotWriter: experiment_run table missing in {db_path!r}. "
                f"Run: python -m scripts.migrate --db {db_path}"
            ) from exc

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def write_experiment_run_start(
        self,
        run_id: str,
        case_id: str,
        agent_id: str,
        config: dict,
        ground_truth_path: str | None = None,
    ) -> None:
        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO experiment_run
                        (run_id, case_id, agent_id, config_json,
                         ground_truth_path, started_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        case_id,
                        agent_id,
                        json.dumps(config, default=str),
                        ground_truth_path,
                        datetime.now(UTC).isoformat(),
                    ),
                )
        except Exception as exc:
            logger.warning("SnapshotWriter.write_experiment_run_start failed: %s", exc)

    def write_experiment_run_complete(
        self,
        run_id: str,
        completed_iterations: int,
        terminated_reason: str,
        total_tokens_in: int,
        total_tokens_out: int,
        total_cost_usd: float,
        final_score: float | None = None,
    ) -> None:
        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    UPDATE experiment_run SET
                        completed_at = ?,
                        completed_iterations = ?,
                        terminated_reason = ?,
                        total_tokens_in = ?,
                        total_tokens_out = ?,
                        total_cost_usd = ?,
                        final_score = ?
                    WHERE run_id = ?
                    """,
                    (
                        datetime.now(UTC).isoformat(),
                        completed_iterations,
                        terminated_reason,
                        total_tokens_in,
                        total_tokens_out,
                        total_cost_usd,
                        final_score,
                        run_id,
                    ),
                )
        except Exception as exc:
            logger.warning("SnapshotWriter.write_experiment_run_complete failed: %s", exc)

    def write_iteration_snapshot(
        self,
        run_id: str,
        case_id: str,
        iteration: int,
        findings: list,
        iocs: list,
        hypotheses: list,
        cumulative_tokens_in: int,
        cumulative_tokens_out: int,
        cumulative_cost_usd: float,
        wall_time_ms: int,
    ) -> None:
        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO iteration_snapshot
                        (run_id, case_id, iteration, findings_json, iocs_json,
                         hypotheses_json, cumulative_tokens_in,
                         cumulative_tokens_out, cumulative_cost_usd,
                         wall_time_ms, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        case_id,
                        iteration,
                        json.dumps(findings, default=str),
                        json.dumps(iocs, default=str),
                        json.dumps(hypotheses, default=str),
                        cumulative_tokens_in,
                        cumulative_tokens_out,
                        cumulative_cost_usd,
                        wall_time_ms,
                        datetime.now(UTC).isoformat(),
                    ),
                )
        except Exception as exc:
            logger.warning("SnapshotWriter.write_iteration_snapshot failed: %s", exc)

    def write_hypothesis_events(
        self,
        run_id: str,
        case_id: str,
        iteration: int,
        events: list[dict],
    ) -> None:
        if not events:
            return
        try:
            with self._conn() as conn:
                for ev in events:
                    conn.execute(
                        """
                        INSERT INTO hypothesis_event
                            (run_id, case_id, iteration, event_type,
                             hypothesis_id, content, confidence, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            case_id,
                            iteration,
                            ev.get("event_type", "formed"),
                            ev.get("hypothesis_id", ""),
                            ev.get("content", ""),
                            ev.get("confidence"),
                            datetime.now(UTC).isoformat(),
                        ),
                    )
        except Exception as exc:
            logger.warning("SnapshotWriter.write_hypothesis_events failed: %s", exc)

    def emit_blocked_mutation(
        self,
        case_id: str,
        attempted_action: str,
        reason: str,
        actor: str = "siftguard-agent",
    ) -> str:
        import uuid

        receipt_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()
        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO blocked_mutation
                        (receipt_id, case_id, attempted_action, reason, actor, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (receipt_id, case_id, attempted_action, reason, actor, timestamp),
                )
        except Exception as exc:
            logger.warning("SnapshotWriter.emit_blocked_mutation failed: %s", exc)
        return receipt_id
