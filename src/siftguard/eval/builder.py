"""TraceBuilder — constructs a Trace from SIFTGuard's SQLite audit DB.

This is SIFTGuard's native adapter. Other agents implement their own
to_trace() adapter; this file is not part of the public framework API.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from siftguard.eval.trace import (
    ExperimentConfig,
    Finding,
    FindingType,
    HypothesisEvent,
    HypothesisEventType,
    IterationSnapshot,
    Orchestrator,
    TerminatedReason,
    Trace,
    TraceMeta,
    ToolCall,
    UsageTotals,
    Verdict,
)


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _require_dt(s: str) -> datetime:
    dt = _parse_dt(s)
    if dt is None:
        raise ValueError(f"Cannot parse datetime: {s!r}")
    return dt


class TraceBuilder:
    """
    Build a Trace from SIFTGuard's audit DB for a given run_id.

    Usage:
        conn = sqlite3.connect("audit/CASE-001.db")
        trace = TraceBuilder(conn).build(run_id)
        json_str = trace.to_json()
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    def build(self, run_id: str) -> Trace:
        run = self._fetch_experiment_run(run_id)
        tool_calls = self._fetch_tool_calls(run_id)
        iterations = self._fetch_iterations(run_id)
        hyp_events = self._fetch_hypothesis_events(run_id)
        findings = self._build_findings(run_id, tool_calls)
        verdict = self._build_verdict(run, findings)
        config = self._build_config(run)
        meta = TraceMeta(
            run_id=run_id,
            agent_id=run["agent_id"],
            case_id=run["case_id"],
            started_at=_require_dt(run["started_at"]),
            completed_at=_parse_dt(run["completed_at"]),
        )
        usage = UsageTotals(
            tokens_in=run["total_tokens_in"] or 0,
            tokens_out=run["total_tokens_out"] or 0,
            cost_usd=run["total_cost_usd"] or 0.0,
            wall_time_ms=self._calc_wall_time(run),
            completed_iterations=run["completed_iterations"] or 0,
        )
        return Trace(
            meta=meta,
            config=config,
            tool_calls=tuple(tool_calls),
            iterations=tuple(iterations),
            hypothesis_events=tuple(hyp_events),
            findings=tuple(findings),
            verdict=verdict,
            usage=usage,
        )

    def _fetch_experiment_run(self, run_id: str) -> sqlite3.Row:
        cur = self.conn.execute(
            "SELECT * FROM experiment_run WHERE run_id = ?", (run_id,)
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"No experiment_run found for run_id={run_id!r}")
        return row

    def _fetch_tool_calls(self, run_id: str) -> list[ToolCall]:
        cur = self.conn.execute(
            """
            SELECT id, tool_name, agent_iteration, outcome,
                   duration_ms, tokens_in, tokens_out, cost_usd, correction_event
            FROM auditentry
            WHERE hypothesis_id LIKE ?
            ORDER BY id
            """,
            (f"{run_id}%",),
        )
        results = []
        for row in cur.fetchall():
            results.append(ToolCall(
                audit_entry_id=row["id"],
                tool_name=row["tool_name"],
                iteration=row["agent_iteration"] or 0,
                outcome=row["outcome"],
                duration_ms=row["duration_ms"],
                tokens_in=row["tokens_in"],
                tokens_out=row["tokens_out"],
                cost_usd=row["cost_usd"],
                correction_event=row["correction_event"],
            ))
        return results

    def _fetch_iterations(self, run_id: str) -> list[IterationSnapshot]:
        cur = self.conn.execute(
            """
            SELECT iteration, findings_json, iocs_json, hypotheses_json,
                   cumulative_tokens_in, cumulative_tokens_out,
                   cumulative_cost_usd, wall_time_ms, created_at
            FROM iteration_snapshot
            WHERE run_id = ?
            ORDER BY iteration
            """,
            (run_id,),
        )
        results = []
        for row in cur.fetchall():
            findings = json.loads(row["findings_json"] or "[]")
            iocs = json.loads(row["iocs_json"] or "[]")
            hyps = json.loads(row["hypotheses_json"] or "[]")
            results.append(IterationSnapshot(
                run_id=run_id,
                iteration=row["iteration"],
                findings_count=len(findings),
                iocs_count=len(iocs),
                hypotheses_count=len(hyps),
                cumulative_tokens_in=row["cumulative_tokens_in"] or 0,
                cumulative_tokens_out=row["cumulative_tokens_out"] or 0,
                cumulative_cost_usd=row["cumulative_cost_usd"] or 0.0,
                wall_time_ms=row["wall_time_ms"],
                created_at=_require_dt(row["created_at"]),
            ))
        return results

    def _fetch_hypothesis_events(self, run_id: str) -> list[HypothesisEvent]:
        cur = self.conn.execute(
            """
            SELECT iteration, event_type, hypothesis_id,
                   content, confidence, created_at
            FROM hypothesis_event
            WHERE run_id = ?
            ORDER BY id
            """,
            (run_id,),
        )
        results = []
        for row in cur.fetchall():
            results.append(HypothesisEvent(
                run_id=run_id,
                iteration=row["iteration"],
                event_type=HypothesisEventType(row["event_type"]),
                hypothesis_id=row["hypothesis_id"],
                content=row["content"],
                confidence=row["confidence"],
                created_at=_require_dt(row["created_at"]),
            ))
        return results

    def _build_findings(
        self,
        run_id: str,
        tool_calls: list[ToolCall],
    ) -> list[Finding]:
        """
        Extract canonical findings from the last iteration snapshot.
        Deduplication key: (type, value.lower()) — per ADR-002.
        """
        cur = self.conn.execute(
            """
            SELECT findings_json, iocs_json
            FROM iteration_snapshot
            WHERE run_id = ?
            ORDER BY iteration DESC
            LIMIT 1
            """,
            (run_id,),
        )
        row = cur.fetchone()
        if row is None:
            return []

        raw_findings = json.loads(row["findings_json"] or "[]")
        seen: set[tuple[str, str]] = set()
        results: list[Finding] = []

        for raw in raw_findings:
            f_type_str = raw.get("type", "other")
            try:
                f_type = FindingType(f_type_str)
            except ValueError:
                f_type = FindingType.OTHER

            value = str(raw.get("value", ""))
            dedup_key = (f_type.value, value.lower())
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            excerpt = str(raw.get("evidence_excerpt", value))[:200]
            if len(excerpt) < 10:
                excerpt = (excerpt + " " * 10)[:10]

            results.append(Finding(
                id=raw.get("id", str(id(raw))),
                type=f_type,
                value=value,
                confidence=raw.get("confidence"),
                supporting_audit_entry_ids=raw.get("audit_entry_ids", []),
                evidence_excerpt=excerpt,
                mitre_technique=raw.get("mitre_technique"),
                first_seen_iteration=raw.get("first_seen_iteration", 0),
            ))
        return results

    def _build_verdict(
        self,
        run: sqlite3.Row,
        findings: list[Finding],
    ) -> Verdict | None:
        terminated = run["terminated_reason"]
        if not terminated:
            return None
        try:
            reason = TerminatedReason(terminated)
        except ValueError:
            reason = TerminatedReason.ERROR

        return Verdict(
            claim=f"Case {run['case_id']}: analysis complete.",
            confidence=run["final_score"],
            supporting_finding_ids=[f.id for f in findings],
            reasoning="See incident report for full reasoning chain.",
            mitre_techniques=list({
                f.mitre_technique
                for f in findings
                if f.mitre_technique
            }),
            terminated_reason=reason,
        )

    def _build_config(self, run: sqlite3.Row) -> ExperimentConfig:
        cfg = json.loads(run["config_json"] or "{}")
        orch_str = cfg.get("orchestrator", "siftguard-native")
        try:
            orch = Orchestrator(orch_str)
        except ValueError:
            orch = Orchestrator.CUSTOM
        return ExperimentConfig(
            agent_id=run["agent_id"],
            model=cfg.get("model", "unknown"),
            orchestrator=orch,
            self_correction=cfg.get("self_correction", True),
            correlation=cfg.get("correlation", True),
            training_mode=cfg.get("training_mode", False),
            max_iterations=cfg.get("max_iterations", 15),
            seed=cfg.get("seed"),
            prompt_version=cfg.get("prompt_version", "v1"),
            notes=cfg.get("notes", ""),
        )

    def _calc_wall_time(self, run: sqlite3.Row) -> int:
        started = _parse_dt(run["started_at"])
        completed = _parse_dt(run["completed_at"])
        if started and completed:
            return int((completed - started).total_seconds() * 1000)
        return 0