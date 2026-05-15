import json, pathlib, pytest
from unittest.mock import patch, mock_open
from src.siftguard.cases.loader import load_manifest
from src.siftguard.eval.ground_truth import CaseManifest, EvidenceLocation

MANIFEST_TEST002 = json.dumps({
    "schema_version": "1.0.0",
    "case_id": "TEST-002",
    "case_name": "NIST CFReDS Hacking Case",
    "evidence_files": [{"path": "/cases/TEST-002/SCHARDT.img", "type": "disk_image", "format": "raw_dd", "filesystem": "ntfs", "os": "windows_xp", "partition_offset_bytes": 32256, "sha256": "abc"}],
    "available_tools": ["filesystem_walk", "mft_parse", "registry_hive_parse", "timeline_build", "file_content_read", "hash_lookup"],
    "unavailable_tools": [
        {"tool": "volatility_pslist",  "reason": "no_memory_image"},
        {"tool": "volatility_netscan", "reason": "no_memory_image"},
        {"tool": "volatility_malfind", "reason": "no_memory_image"},
        {"tool": "volatility_handles", "reason": "no_memory_image"}
    ],
    "ground_truth_path": "experiments/ground_truth/TEST-002-v1.1.0.json"
})


def _make_manifest() -> CaseManifest:
    return CaseManifest.model_validate_json(MANIFEST_TEST002)


def test_manifest_parses():
    m = _make_manifest()
    assert m.case_id == "TEST-002"
    assert len(m.available_tools) == 6
    assert len(m.unavailable_tools) == 4


def test_volatility_unavailable():
    m = _make_manifest()
    assert not m.is_tool_available("volatility_pslist")
    assert not m.is_tool_available("volatility_netscan")


def test_disk_tools_available():
    m = _make_manifest()
    assert m.is_tool_available("mft_parse")
    assert m.is_tool_available("registry_hive_parse")


def test_reachable_disk_only_ioc(tmp_path):
    from src.siftguard.eval.ground_truth import IOCExpectation, EvidenceLocation
    m = _make_manifest()
    ioc = IOCExpectation(
        ioc_id="ioc-file-netstumbler",
        ioc_type="file",
        expected={"filename_pattern": "*netstumbler*"},
        confidence_threshold=0.8,
        evidence_location=EvidenceLocation.DISK_ONLY,
        rationale="test"
    )
    assert m.reachable(ioc) is True


def test_not_reachable_memory_only_ioc():
    from src.siftguard.eval.ground_truth import IOCExpectation, EvidenceLocation
    m = _make_manifest()
    ioc = IOCExpectation(
        ioc_id="ioc-proc-test",
        ioc_type="process",
        expected={"pid": 999},
        confidence_threshold=0.8,
        evidence_location=EvidenceLocation.MEMORY_ONLY,
        rationale="test"
    )
    assert m.reachable(ioc) is False


def test_applicable_iocs_count():
    """Scorer denominator = applicable only, never total."""
    from src.siftguard.eval.ground_truth import IOCExpectation, EvidenceLocation, GroundTruth
    m = _make_manifest()
    gt_data = {
        "schema_version": "1.1.0",
        "case_id": "TEST-002",
        "case_name": "test",
        "iocs": [
            {"ioc_id": "ioc-file-a", "ioc_type": "file", "expected": {}, "confidence_threshold": 0.8, "evidence_location": "disk_only", "rationale": "r"},
            {"ioc_id": "ioc-proc-b", "ioc_type": "process", "expected": {}, "confidence_threshold": 0.8, "evidence_location": "memory_only", "rationale": "r"},
        ]
    }
    gt = GroundTruth.model_validate(gt_data)
    applicable = [ioc for ioc in gt.iocs if m.reachable(ioc)]
    assert len(applicable) == 1  # only disk_only passes