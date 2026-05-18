import os
import sqlite3
import tempfile

import pytest

from siftguard.eval.analytics.correction_panel import get_correction_breakdown
from siftguard.models.correction_taxonomy import SelfCorrectionType, classify_correction


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Pydantic validation error on output schema", SelfCorrectionType.FORMAT_RETRY),
        ("Invalid JSON returned, parse error", SelfCorrectionType.FORMAT_RETRY),
        ("Volatility tool failed, retrying tool call", SelfCorrectionType.TOOL_RETRY),
        ("Subprocess command failed on windows.psscan", SelfCorrectionType.TOOL_RETRY),
        (
            "Verdict revised after reviewing new memory artifact",
            SelfCorrectionType.VERDICT_REVISION,
        ),
        ("Updated verdict from INCONCLUSIVE to MALICIOUS", SelfCorrectionType.VERDICT_REVISION),
        ("IOC 172.16.4.10 added to indicator list", SelfCorrectionType.IOC_REVISION),
        ("Retrying section — empty result from MFT scan", SelfCorrectionType.SECTION_REFILL),
        (
            "Retracting finding — unverifiable in memory image",
            SelfCorrectionType.HALLUCINATION_RETRACT,
        ),
        ("Cannot confirm process injection claim", SelfCorrectionType.HALLUCINATION_RETRACT),
        ("Reducing confidence score for lateral movement", SelfCorrectionType.CONFIDENCE_DOWNGRADE),
        ("Expanding scope — new lead found in registry hive", SelfCorrectionType.SCOPE_EXPANSION),
        ("Some completely unrelated log message", SelfCorrectionType.UNKNOWN),
        ("", SelfCorrectionType.UNKNOWN),
    ],
)
def test_classifier_rules(message, expected):
    assert classify_correction(message) == expected


def test_unknown_fallback():
    assert classify_correction("nothing matches here xyz") == SelfCorrectionType.UNKNOWN


def _make_mock_db(rows: list[dict]) -> str:
    tmp = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(tmp)
    conn.execute("""
        CREATE TABLE auditentry (
            id INTEGER PRIMARY KEY,
            case_id TEXT NOT NULL,
            timestamp TEXT NOT NULL DEFAULT '',
            tool_name TEXT NOT NULL DEFAULT '',
            tool_version TEXT NOT NULL DEFAULT '',
            args_json TEXT NOT NULL DEFAULT '',
            args_sha256 TEXT NOT NULL DEFAULT '',
            outcome TEXT NOT NULL DEFAULT '',
            output_sha256 TEXT NOT NULL DEFAULT '',
            output_excerpt TEXT NOT NULL DEFAULT '',
            duration_ms INTEGER NOT NULL DEFAULT 0,
            agent_iteration INTEGER,
            correction_event TEXT
        )
    """)
    for r in rows:
        conn.execute(
            "INSERT INTO auditentry (id, case_id, agent_iteration, tool_name, correction_event) VALUES (?,?,?,?,?)",
            (
                r["id"],
                r["case_id"],
                r.get("agent_iteration", 1),
                r.get("tool_name", ""),
                r.get("correction_event"),
            ),
        )
    conn.commit()
    conn.close()
    return tmp


def test_breakdown_shape():
    db = _make_mock_db(
        [
            {
                "id": 1,
                "case_id": "CASE-001",
                "agent_iteration": 1,
                "correction_event": "Pydantic validation error",
            },
            {
                "id": 2,
                "case_id": "CASE-001",
                "agent_iteration": 1,
                "correction_event": "Volatility tool failed",
            },
            {
                "id": 3,
                "case_id": "CASE-001",
                "agent_iteration": 2,
                "correction_event": "Verdict revised",
            },
            {
                "id": 4,
                "case_id": "CASE-001",
                "agent_iteration": 2,
                "correction_event": "nothing matches",
            },
            {
                "id": 5,
                "case_id": "CASE-001",
                "agent_iteration": 2,
                "correction_event": None,
            },  # excluded
        ]
    )
    try:
        result = get_correction_breakdown(db, "CASE-001")
        assert result["total_corrections"] == 4
        assert result["breakdown_by_type"]["FORMAT_RETRY"] == 1
        assert result["breakdown_by_type"]["TOOL_RETRY"] == 1
        assert result["breakdown_by_type"]["VERDICT_REVISION"] == 1
        assert result["breakdown_by_type"]["UNKNOWN"] == 1
        assert result["unknown_pct"] == 25.0
        assert len(result["breakdown_by_iteration"]["1"]) == 2
        assert len(result["breakdown_by_iteration"]["2"]) == 2
        assert len(result["events"]) == 4
    finally:
        os.unlink(db)


def test_breakdown_empty():
    db = _make_mock_db([])
    try:
        result = get_correction_breakdown(db, "CASE-001")
        assert result["total_corrections"] == 0
        assert result["unknown_pct"] == 0.0
        assert result["events"] == []
    finally:
        os.unlink(db)


def test_filters_by_case_id():
    db = _make_mock_db(
        [
            {
                "id": 1,
                "case_id": "CASE-001",
                "agent_iteration": 1,
                "correction_event": "tool failed",
            },
            {
                "id": 2,
                "case_id": "CASE-999",
                "agent_iteration": 1,
                "correction_event": "tool failed",
            },
        ]
    )
    try:
        result = get_correction_breakdown(db, "CASE-001")
        assert result["total_corrections"] == 1
    finally:
        os.unlink(db)


def test_null_correction_events_excluded():
    db = _make_mock_db(
        [
            {"id": 1, "case_id": "CASE-001", "agent_iteration": 1, "correction_event": None},
            {"id": 2, "case_id": "CASE-001", "agent_iteration": 1, "correction_event": None},
        ]
    )
    try:
        result = get_correction_breakdown(db, "CASE-001")
        assert result["total_corrections"] == 0
    finally:
        os.unlink(db)
