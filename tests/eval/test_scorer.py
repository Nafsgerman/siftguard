"""tests/eval/test_scorer.py"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from siftguard.eval.scorer import (
    EXTRACTORS,
    IOC_PRODUCING_TOOLS,
    ScoreResult,
    _prf,
    extract_findings_from_db,
    get_last_run_id,
    load_ground_truth,
    score_run,
    score_run_from_report,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gt_dir(tmp_path: Path) -> Path:
    return tmp_path / "ground_truth"


@pytest.fixture
def simple_gt(gt_dir: Path) -> Path:
    gt_dir.mkdir(parents=True, exist_ok=True)
    gt = {
        "case_id": "TEST-001",
        "version": "1.1.0",
        "iocs": [
            {
                "ioc_id": "proc-001",
                "ioc_type": "process",
                "value": "1234:evil.exe",
                "evidence_location": ["windows_psscan"],
            },
            {
                "ioc_id": "net-001",
                "ioc_type": "network_connection",
                "value": "192.168.1.100:4444",
                "evidence_location": ["windows_netscan"],
            },
            {
                "ioc_id": "disk-001",
                "ioc_type": "file",
                "value": "evil.dat",
                "evidence_location": ["linux_bash_history"],  # NOT in IOC_PRODUCING_TOOLS
            },
        ],
    }
    path = gt_dir / "TEST-001-v1.1.0.json"
    path.write_text(json.dumps(gt))
    return gt_dir


@pytest.fixture
def audit_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "TEST-001.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("""
            CREATE TABLE auditentry (
                id INTEGER PRIMARY KEY,
                run_id TEXT,
                agent_id TEXT,
                case_id TEXT,
                event_type TEXT,
                tool_name TEXT,
                tool_input TEXT,
                tool_output TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Matching run — psscan hit
        conn.execute(
            "INSERT INTO auditentry (run_id, agent_id, case_id, event_type, tool_name, tool_output) VALUES (?,?,?,?,?,?)",
            (
                "run-abc",
                "siftguard-v2",
                "TEST-001",
                "tool_call_end",
                "windows_psscan",
                json.dumps([{"PID": 1234, "ImageFileName": "evil.exe"}]),
            ),
        )
        # Matching run — netscan hit
        conn.execute(
            "INSERT INTO auditentry (run_id, agent_id, case_id, event_type, tool_name, tool_output) VALUES (?,?,?,?,?,?)",
            (
                "run-abc",
                "siftguard-v2",
                "TEST-001",
                "tool_call_end",
                "windows_netscan",
                json.dumps([{"ForeignAddr": "192.168.1.100", "ForeignPort": 4444}]),
            ),
        )
        # Different run — should be ignored
        conn.execute(
            "INSERT INTO auditentry (run_id, agent_id, case_id, event_type, tool_name, tool_output) VALUES (?,?,?,?,?,?)",
            (
                "run-xyz",
                "siftguard-v2",
                "TEST-001",
                "tool_call_end",
                "windows_psscan",
                json.dumps([{"PID": 9999, "ImageFileName": "legit.exe"}]),
            ),
        )
        # Non-IOC tool — should be ignored
        conn.execute(
            "INSERT INTO auditentry (run_id, agent_id, case_id, event_type, tool_name, tool_output) VALUES (?,?,?,?,?,?)",
            (
                "run-abc",
                "siftguard-v2",
                "TEST-001",
                "tool_call_end",
                "read_file",
                json.dumps([{"content": "evil.dat"}]),
            ),
        )
        conn.commit()
    return db_path


# ---------------------------------------------------------------------------
# Unit: IOC_PRODUCING_TOOLS
# ---------------------------------------------------------------------------


class TestIOCProducingTools:
    def test_allowlist_is_frozenset(self):
        assert isinstance(IOC_PRODUCING_TOOLS, frozenset)

    def test_core_tools_present(self):
        required = {"windows_psscan", "windows_netscan", "windows_malfind"}
        assert required.issubset(IOC_PRODUCING_TOOLS)

    def test_read_file_not_in_allowlist(self):
        assert "read_file" not in IOC_PRODUCING_TOOLS

    def test_list_directory_not_in_allowlist(self):
        assert "list_directory" not in IOC_PRODUCING_TOOLS


# ---------------------------------------------------------------------------
# Unit: extractors
# ---------------------------------------------------------------------------


class TestExtractors:
    def test_psscan_extracts_pid_name(self):
        rows = [{"PID": 1234, "ImageFileName": "Evil.exe"}]
        result = EXTRACTORS["windows_psscan"](rows)
        assert "1234:evil.exe" in result

    def test_psscan_empty_rows(self):
        assert EXTRACTORS["windows_psscan"]([]) == set()

    def test_netscan_extracts_addr_port(self):
        rows = [{"ForeignAddr": "10.0.0.1", "ForeignPort": 4444}]
        result = EXTRACTORS["windows_netscan"](rows)
        assert "10.0.0.1:4444" in result

    def test_netscan_skips_wildcard(self):
        rows = [{"ForeignAddr": "*", "ForeignPort": 0}]
        result = EXTRACTORS["windows_netscan"](rows)
        assert len(result) == 0

    def test_malfind_extracts_pid_start(self):
        rows = [{"PID": 888, "Start": "0xDEAD0000"}]
        result = EXTRACTORS["windows_malfind"](rows)
        assert "888:0xdead0000" in result

    def test_registry_extracts_key_name(self):
        rows = [{"Key": "HKLM\\Run", "Name": "Persist", "Data": "evil.exe"}]
        result = EXTRACTORS["windows_registry_printkey"](rows)
        assert "hklm\\run:persist" in result
        assert "data:evil.exe" in result

    def test_mftscan_extracts_filename(self):
        rows = [{"Filename": "C:\\Windows\\evil.exe"}]
        result = EXTRACTORS["windows_mftscan"](rows)
        assert "c:\\windows\\evil.exe" in result

    def test_mftscan_ads_extracts_filename_ads(self):
        rows = [{"Filename": "legit.txt", "ADSFilename": "hidden:$DATA"}]
        result = EXTRACTORS["windows_mftscan_ads"](rows)
        assert "legit.txt:hidden:$data" in result

    def test_all_tools_have_extractor(self):
        for tool in IOC_PRODUCING_TOOLS:
            assert tool in EXTRACTORS, f"No extractor for {tool}"


# ---------------------------------------------------------------------------
# Unit: ground truth loader
# ---------------------------------------------------------------------------


class TestLoadGroundTruth:
    def test_loads_valid_file(self, simple_gt: Path):
        gt = load_ground_truth("TEST-001", "1.1.0", gt_root=simple_gt)
        assert gt.case_id == "TEST-001"
        assert len(gt.iocs) == 3

    def test_values_normalized_to_lowercase(self, simple_gt: Path):
        gt = load_ground_truth("TEST-001", "1.1.0", gt_root=simple_gt)
        for ioc in gt.iocs:
            assert ioc.value == ioc.value.lower()

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_ground_truth("NONEXISTENT", "9.9.9", gt_root=tmp_path)


# ---------------------------------------------------------------------------
# Unit: extract_findings_from_db
# ---------------------------------------------------------------------------


class TestExtractFindingsFromDB:
    def test_extracts_correct_run(self, audit_db: Path):
        found = extract_findings_from_db(audit_db, "run-abc")
        assert "1234:evil.exe" in found
        assert "192.168.1.100:4444" in found

    def test_ignores_other_run(self, audit_db: Path):
        found = extract_findings_from_db(audit_db, "run-abc")
        assert "9999:legit.exe" not in found

    def test_ignores_non_ioc_tool(self, audit_db: Path):
        found = extract_findings_from_db(audit_db, "run-abc")
        # read_file output should not appear
        for key in found:
            assert "evil.dat" not in key or "windows_" in key  # only if from an IOC tool

    def test_missing_db_returns_empty(self, tmp_path: Path):
        found = extract_findings_from_db(tmp_path / "missing.db", "run-abc")
        assert found == set()

    def test_returns_set(self, audit_db: Path):
        assert isinstance(extract_findings_from_db(audit_db, "run-abc"), set)


# ---------------------------------------------------------------------------
# Unit: get_last_run_id
# ---------------------------------------------------------------------------


class TestGetLastRunId:
    def test_returns_most_recent_run_id(self, audit_db: Path):
        run_id = get_last_run_id(audit_db, "siftguard-v2", "TEST-001")
        assert run_id is not None

    def test_missing_db_returns_none(self, tmp_path: Path):
        run_id = get_last_run_id(tmp_path / "missing.db", "siftguard-v2", "TEST-001")
        assert run_id is None


# ---------------------------------------------------------------------------
# Unit: _prf
# ---------------------------------------------------------------------------


class TestPRF:
    def test_perfect_score(self):
        p, r, f1 = _prf(tp=5, fp=0, fn=0)
        assert p == pytest.approx(1.0)
        assert r == pytest.approx(1.0)
        assert f1 == pytest.approx(1.0)

    def test_zero_tp(self):
        p, r, f1 = _prf(tp=0, fp=3, fn=2)
        assert p == pytest.approx(0.0)
        assert r == pytest.approx(0.0)
        assert f1 == pytest.approx(0.0)

    def test_no_predictions(self):
        p, r, f1 = _prf(tp=0, fp=0, fn=5)
        assert p is None  # no predictions → precision undefined
        assert r == pytest.approx(0.0)

    def test_balanced(self):
        p, r, f1 = _prf(tp=3, fp=1, fn=1)
        assert p == pytest.approx(0.75)
        assert r == pytest.approx(0.75)
        assert f1 == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# Integration: score_run
# ---------------------------------------------------------------------------


class TestScoreRun:
    def test_perfect_score_applicable(self, audit_db: Path, simple_gt: Path):
        # GT has 2 applicable IOCs (psscan + netscan), both found in DB for run-abc
        result = score_run(
            case_id="TEST-001",
            agent_id="siftguard-v2",
            gt_version="1.1.0",
            audit_db_path=audit_db,
            run_id="run-abc",
            gt_root=simple_gt,
        )
        assert isinstance(result, ScoreResult)
        assert result.applicable_count == 2
        assert result.total_count == 3
        assert result.tp == 2
        assert result.f1_applicable == pytest.approx(1.0)

    def test_no_applicable_iocs_returns_none(self, audit_db: Path, tmp_path: Path):
        gt_dir = tmp_path / "gt"
        gt_dir.mkdir()
        gt = {
            "case_id": "TEST-001",
            "version": "1.1.0",
            "iocs": [
                {
                    "ioc_id": "x-001",
                    "ioc_type": "file",
                    "value": "something",
                    "evidence_location": ["linux_bash_history"],
                }
            ],
        }
        (gt_dir / "TEST-001-v1.1.0.json").write_text(json.dumps(gt))
        result = score_run(
            case_id="TEST-001",
            agent_id="siftguard-v2",
            gt_version="1.1.0",
            audit_db_path=audit_db,
            run_id="run-abc",
            gt_root=gt_dir,
        )
        assert result.f1_applicable is None
        assert result.applicable_count == 0

    def test_result_has_to_dict(self, audit_db: Path, simple_gt: Path):
        result = score_run(
            case_id="TEST-001",
            agent_id="siftguard-v2",
            gt_version="1.1.0",
            audit_db_path=audit_db,
            run_id="run-abc",
            gt_root=simple_gt,
        )
        d = result.to_dict()
        assert "f1_applicable" in d
        assert "f1_total" in d
        assert "run_id" in d

    def test_partial_recall(self, tmp_path: Path):
        # Only psscan in DB, netscan missing → recall = 0.5
        db_path = tmp_path / "partial.db"
        gt_dir = tmp_path / "gt"
        gt_dir.mkdir()
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("""
                CREATE TABLE auditentry (
                    id INTEGER PRIMARY KEY, run_id TEXT, agent_id TEXT, case_id TEXT,
                    event_type TEXT, tool_name TEXT, tool_input TEXT, tool_output TEXT
                )
            """)
            conn.execute(
                "INSERT INTO auditentry VALUES (1,'r1','a1','TEST-001','tool_call_end','windows_psscan',NULL,?)",
                (json.dumps([{"PID": 1234, "ImageFileName": "evil.exe"}]),),
            )
            conn.commit()
        gt = {
            "case_id": "TEST-001",
            "version": "1.1.0",
            "iocs": [
                {
                    "ioc_id": "p1",
                    "ioc_type": "process",
                    "value": "1234:evil.exe",
                    "evidence_location": ["windows_psscan"],
                },
                {
                    "ioc_id": "n1",
                    "ioc_type": "network_connection",
                    "value": "1.2.3.4:4444",
                    "evidence_location": ["windows_netscan"],
                },
            ],
        }
        (gt_dir / "TEST-001-v1.1.0.json").write_text(json.dumps(gt))
        result = score_run("TEST-001", "a1", "1.1.0", db_path, "r1", gt_root=gt_dir)
        assert result.recall_applicable == pytest.approx(0.5)
        assert result.tp == 1
        assert result.fn_applicable == 1


# ---------------------------------------------------------------------------
# Integration: score_run_from_report (degraded path)
# ---------------------------------------------------------------------------


class TestScoreRunFromReport:
    def test_recall_from_report(self, simple_gt: Path):
        report = (
            "Found process evil.exe on PID 1234. Network connection 192.168.1.100:4444 detected."
        )
        result = score_run_from_report(
            case_id="TEST-001",
            agent_id="siftguard-v2",
            gt_version="1.1.0",
            report_text=report,
            gt_root=simple_gt,
        )
        assert result.precision_applicable is None
        assert result.f1_applicable is None
        assert result.recall_applicable is not None
        assert result.recall_applicable > 0

    def test_run_id_is_report_marker(self, simple_gt: Path):
        result = score_run_from_report("TEST-001", "a", "1.1.0", "nothing", gt_root=simple_gt)
        assert result.run_id == "<report>"
