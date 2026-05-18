"""Tests for cases.loader — single source of truth for case manifests.

ADR-008: flat datasets/registry.py deleted; loader.py is canonical.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from siftguard.cases.loader import (
    evidence_paths,
    get_case,
    ground_truth_path,
    list_case_ids,
    list_cases,
)
from siftguard.eval.ground_truth import CaseManifest

KNOWN_CASES = ["TEST-001", "TEST-002"]


@pytest.mark.parametrize("case_id", KNOWN_CASES)
def test_manifest_loads(case_id: str) -> None:
    manifest = get_case(case_id)
    assert manifest.case_id == case_id
    assert manifest.schema_version == "1.0.0"
    assert manifest.case_name
    assert manifest.briefing


@pytest.mark.parametrize("case_id", KNOWN_CASES)
def test_manifest_has_evidence_files(case_id: str) -> None:
    manifest = get_case(case_id)
    assert len(manifest.evidence_files) >= 1
    for ef in manifest.evidence_files:
        assert "path" in ef
        assert "type" in ef


@pytest.mark.parametrize("case_id", KNOWN_CASES)
def test_manifest_has_available_tools(case_id: str) -> None:
    manifest = get_case(case_id)
    assert len(manifest.available_tools) >= 1


@pytest.mark.parametrize("case_id", KNOWN_CASES)
def test_threat_type_set(case_id: str) -> None:
    manifest = get_case(case_id)
    assert manifest.threat_type != "unknown"


def test_list_case_ids_contains_known() -> None:
    ids = list_case_ids()
    for cid in KNOWN_CASES:
        assert cid in ids, f"{cid} missing from list_case_ids()"


def test_list_cases_returns_manifests() -> None:
    cases = list_cases()
    assert len(cases) >= 2
    assert all(isinstance(c, CaseManifest) for c in cases)


def test_list_case_ids_sorted() -> None:
    ids = list_case_ids()
    assert ids == sorted(ids)


@pytest.mark.parametrize("case_id", KNOWN_CASES)
def test_evidence_paths_returns_dict(case_id: str) -> None:
    manifest = get_case(case_id)
    paths = evidence_paths(manifest)
    assert isinstance(paths, dict)
    assert len(paths) >= 1
    for key, val in paths.items():
        assert isinstance(val, Path)


def test_test001_has_memory_image() -> None:
    manifest = get_case("TEST-001")
    paths = evidence_paths(manifest)
    assert "memory_image" in paths


def test_test002_has_disk_image() -> None:
    manifest = get_case("TEST-002")
    paths = evidence_paths(manifest)
    assert "disk_image" in paths


def test_test001_no_disk_image() -> None:
    manifest = get_case("TEST-001")
    paths = evidence_paths(manifest)
    assert "disk_image" not in paths


def test_test002_no_memory_image() -> None:
    manifest = get_case("TEST-002")
    paths = evidence_paths(manifest)
    assert "memory_image" not in paths


def test_ground_truth_path_returns_path() -> None:
    manifest = get_case("TEST-001")
    p = ground_truth_path(manifest)
    assert isinstance(p, Path)


def test_missing_case_raises() -> None:
    with pytest.raises(FileNotFoundError):
        get_case("TEST-NONEXISTENT")


def test_get_case_is_cached() -> None:
    m1 = get_case("TEST-001")
    m2 = get_case("TEST-001")
    assert m1 is m2  # lru_cache hit


@pytest.mark.parametrize(
    "case_id,unavailable_tool",
    [
        ("TEST-002", "volatility_pslist"),
        ("TEST-001", "filesystem_walk"),
    ],
)
def test_tool_unavailable(case_id: str, unavailable_tool: str) -> None:
    manifest = get_case(case_id)
    assert not manifest.is_tool_available(unavailable_tool)
