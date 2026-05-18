from __future__ import annotations

import os
import sqlite3
import tempfile

from siftguard.eval.verifier import verify_finding
from siftguard.eval.verifier_models import VerificationMethod, VerificationStatus


def _make_db(tool_outputs: list) -> str:
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db.close()
    con = sqlite3.connect(db.name)
    con.execute(
        "CREATE TABLE auditentry (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, tool_output TEXT, correction_event TEXT)"
    )
    for out in tool_outputs:
        con.execute("INSERT INTO auditentry (run_id, tool_output) VALUES (?, ?)", ("RUN-001", out))
    con.commit()
    con.close()
    return db.name


def test_exact_match_verified():
    db = _make_db(["C2 detected at 172.16.4.10:8080 outbound connection"])
    result = verify_finding(
        {
            "id": "F-001",
            "value": "172.16.4.10:8080",
            "type": "network",
            "description": "C2 channel",
        },
        db,
        "RUN-001",
    )
    os.unlink(db)
    assert result.status == VerificationStatus.VERIFIED
    assert result.method == VerificationMethod.SUBSTRING_MATCH
    assert result.confidence >= 0.90
    assert "172.16.4.10:8080" in result.matched_evidence.lower()


def test_substring_match_partial_value():
    db = _make_db(["Backdoor process listening on port 5682, pid=1337"])
    result = verify_finding(
        {"id": "F-002", "value": "5682", "type": "network", "description": "backdoor port"},
        db,
        "RUN-001",
    )
    os.unlink(db)
    assert result.status == VerificationStatus.VERIFIED
    assert result.method == VerificationMethod.SUBSTRING_MATCH


def test_description_keyword_fallback():
    db = _make_db(["registry persistence detected under CurrentVersion\\Run"])
    result = verify_finding(
        {
            "id": "F-003",
            "value": "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run\\Backdoor",
            "type": "registry",
            "description": "persistence registry key for malware startup",
        },
        db,
        "RUN-001",
    )
    os.unlink(db)
    assert result.status == VerificationStatus.VERIFIED
    assert result.confidence <= 0.80


def test_paraphrase_miss_refuted():
    db = _make_db(["completely unrelated tool output about file timestamps"])
    result = verify_finding(
        {"id": "F-004", "value": "33001", "type": "network", "description": "second backdoor port"},
        db,
        "RUN-001",
    )
    os.unlink(db)
    assert result.status == VerificationStatus.REFUTED
    assert result.refutation_reason is not None


def test_empty_audit_corpus():
    db = _make_db([])
    result = verify_finding(
        {"id": "F-005", "value": "172.16.4.10", "type": "network", "description": "C2 IP"},
        db,
        "RUN-001",
    )
    os.unlink(db)
    assert result.status == VerificationStatus.UNVERIFIABLE
    assert result.method == VerificationMethod.UNVERIFIABLE
    assert "empty" in result.refutation_reason


def test_empty_finding_value():
    db = _make_db(["some output"])
    result = verify_finding(
        {"id": "F-006", "value": "", "type": "network", "description": "missing value"},
        db,
        "RUN-001",
    )
    os.unlink(db)
    assert result.status == VerificationStatus.UNVERIFIABLE


def test_whitelisted_process_verified():
    db = _make_db([])
    result = verify_finding(
        {
            "id": "F-007",
            "value": "svchost.exe",
            "type": "process",
            "description": "windows service host",
        },
        db,
        "RUN-001",
    )
    os.unlink(db)
    assert result.status == VerificationStatus.VERIFIED
    assert result.confidence == 1.0


def test_tool_rerun_path_refuted(monkeypatch):
    db = _make_db(["unrelated output only"])
    monkeypatch.setattr("siftguard.eval.verifier._tool_rerun_verify", lambda v, t: None)
    result = verify_finding(
        {"id": "F-008", "value": "172.16.4.10", "type": "network", "description": "C2 IP"},
        db,
        "RUN-001",
        enable_tool_rerun=True,
    )
    os.unlink(db)
    assert result.status == VerificationStatus.REFUTED
    assert result.method == VerificationMethod.TOOL_RERUN


def test_tool_rerun_path_verified(monkeypatch):
    db = _make_db(["unrelated output only"])
    monkeypatch.setattr(
        "siftguard.eval.verifier._tool_rerun_verify",
        lambda v, t: "TCPv4 ESTABLISHED 172.16.4.10:8080 pid=666",
    )
    result = verify_finding(
        {"id": "F-009", "value": "172.16.4.10", "type": "network", "description": "C2 IP"},
        db,
        "RUN-001",
        enable_tool_rerun=True,
    )
    os.unlink(db)
    assert result.status == VerificationStatus.VERIFIED
    assert result.method == VerificationMethod.TOOL_RERUN
    assert result.confidence == 0.99
