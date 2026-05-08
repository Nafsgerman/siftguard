from __future__ import annotations

import sqlite3
import tempfile
import os
import pytest

from siftguard.eval.verifier import verify_finding
from siftguard.eval.verifier_models import VerificationStatus, VerificationMethod


# ── fixtures ────────────────────────────────────────────────────────────────

def _make_db(tool_outputs: list[str]) -> str:
    """Create a temp SQLite DB with auditentry rows and return path."""
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db.close()
    con = sqlite3.connect(db.name)
    con.execute("""
        CREATE TABLE auditentry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            tool_output TEXT,
            correction_event TEXT
        )
    """)
    for out in tool_outputs:
        con.execute(
            "INSERT INTO auditentry (run_id, tool_output) VALUES (?, ?)",
            ("RUN-001", out),
        )
    con.commit()
    con.close()
    return db.name


# ── exact match ─────────────────────────────────────────────────────────────

def test_exact_match_verified():
    db = _make_db(["C2 detected at 172.16.4.10:8080 outbound connection"])
    finding = {"id": "F-001", "value": "172.16.4.10:8080", "type": "network", "description": "C2 channel"}
    result = verify_finding(finding, db, "RUN-001")
    os.unlink(db)
    assert result.status == VerificationStatus.VERIFIED
    assert result.method == VerificationMethod.SUBSTRING_MATCH
    assert result.confidence >= 0.90
    assert "172.16.4.10:8080" in result.matched_evidence.lower()


# ── substring match ──────────────────────────────────────────────────────────

def test_substring_match_partial_value():
    db = _make_db(["Backdoor process listening on port 5682, pid=1337"])
    finding = {"id": "F-002", "value": "5682", "type": "network", "description": "backdoor port"}
    result = verify_finding(finding, db, "RUN-001")
    os.unlink(db)
    assert result.status == VerificationStatus.VERIFIED
    assert result.method == VerificationMethod.SUBSTRING_MATCH


# ── description keyword fallback ─────────────────────────────────────────────

def test_description_keyword_fallback():
    # value not in corpus, but description keyword is
    db = _make_db(["registry persistence detected under CurrentVersion\\Run"])
    finding = {
        "id": "F-003",
        "value": "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run\\Backdoor",
        "type": "registry",
        "description": "persistence registry key for malware startup",
    }
    result = verify_finding(finding, db, "RUN-001")
    os.unlink(db)
    # description token "persistence" or "registry" should match
    assert result.status == VerificationStatus.VERIFIED
    assert result.confidence <= 0.80  # lower confidence on description match


# ── paraphrase miss → refuted ────────────────────────────────────────────────

def test_paraphrase_miss_refuted():
    db = _make_db(["completely unrelated tool output about file timestamps"])
    finding = {"id": "F-004", "value": "33001", "type": "network", "description": "second backdoor port"}
    result = verify_finding(finding, db, "RUN-001")
    os.unlink(db)
    assert result.status == VerificationStatus.REFUTED
    assert result.refutation_reason is not None


# ── empty audit corpus ───────────────────────────────────────────────────────

def test_empty_audit_corpus():
    db = _make_db([])  # no rows
    finding = {"id": "F-005", "value": "172.16.4.10", "type": "network", "description": "C2 IP"}
    result = verify_finding(finding, db, "RUN-001")
    os.unlink(db)
    assert result.status == VerificationStatus.UNVERIFIABLE
    assert result.method == VerificationMethod.UNVERIFIABLE
    assert "empty" in result.refutation_reason


# ── empty finding value ──────────────────────────────────────────────────────

def test_empty_finding_value():
    db = _make_db(["some output"])
    finding = {"id": "F-006", "value": "", "type": "network", "description": "missing value"}
    result = verify_finding(finding, db, "RUN-001")
    os.unlink(db)
    assert result.status == VerificationStatus.UNVERIFIABLE


# ── whitelist ────────────────────────────────────────────────────────────────

def test_whitelisted_process_verified():
    db = _make_db([])  # empty corpus — whitelist should short-circuit
    finding = {"id": "F-007", "value": "svchost.exe", "type": "process", "description": "windows service host"}
    result = verify_finding(finding, db, "RUN-001")
    os.unlink(db)
    assert result.status == VerificationStatus.VERIFIED
    assert result.confidence == 1.0


# ── tool re-run path (mocked) ────────────────────────────────────────────────

def test_tool_rerun_path_refuted(monkeypatch):
    """Slow path: tool re-run returns no match → REFUTED."""
    db = _make_db(["unrelated output only"])

    def mock_tool_rerun(value, ftype):
        return None  # simulate: not found in fresh vol output

    monkeypatch.setattr("siftguard.eval.verifier._tool_rerun_verify", mock_tool_rerun)

    finding = {"id": "F-008", "value": "172.16.4.10", "type": "network", "description": "C2 IP"}
    result = verify_finding(finding, db, "RUN-001", enable_tool_rerun=True)
    os.unlink(db)
    assert result.status == VerificationStatus.REFUTED
    assert result.method == VerificationMethod.TOOL_RERUN


def test_tool_rerun_path_verified(monkeypatch):
    """Slow path: tool re-run finds the value → VERIFIED at 0.99."""
    db = _make_db(["unrelated output only"])

    def mock_tool_rerun(value, ftype):
        return f"TCPv4 ESTABLISHED 172.16.4.10:8080 pid=666"

    monkeypatch.setattr("siftguard.eval.verifier._tool_rerun_verify", mock_tool_rerun)

    finding = {"id": "F-009", "value": "172.16.4.10", "type": "network", "description": "C2 IP"}
    result = verify_finding(finding, db, "RUN-001", enable_tool_rerun=True)
    os.unlink(db)
    assert result.status == VerificationStatus.VERIFIED
    assert result.method == VerificationMethod.TOOL_RERUN
    assert result.confidence == 0.99