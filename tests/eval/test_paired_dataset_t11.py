"""T11: Paired dataset — TEST-001 (memory) + TEST-002 (disk) load and score consistently."""

from pathlib import Path

import pytest

from siftguard.eval.scorer import load_ground_truth

REPO_ROOT = Path(__file__).resolve().parents[2]
GT_ROOT = REPO_ROOT / "experiments" / "ground_truth"


@pytest.mark.parametrize("case_id,min_iocs", [("TEST-001", 4), ("TEST-002", 7)])
def test_ground_truth_loads(case_id, min_iocs):
    """Both cases must load via the v1.1.0 loader without exceptions."""
    gt = load_ground_truth(case_id, "1.1.0", GT_ROOT)
    assert gt.case_id == case_id
    assert gt.version == "1.1.0"
    assert len(gt.iocs) >= min_iocs


def test_test001_iocs_are_memory_surface():
    """TEST-001 (memory) IOCs must reference Volatility tools, not disk tools."""
    gt = load_ground_truth("TEST-001", "1.1.0", GT_ROOT)
    disk_tools = {"filesystem_walk", "mft_parse", "registry_hive_parse"}
    for ioc in gt.iocs:
        tools = set(ioc.evidence_location)
        assert not (tools & disk_tools), (
            f"TEST-001 IOC {ioc.ioc_id} references disk tool {tools & disk_tools}; "
            f"memory case must use Volatility surface"
        )


def test_test002_iocs_are_disk_surface():
    """TEST-002 (disk) IOCs must reference disk/registry tools, not Volatility."""
    gt = load_ground_truth("TEST-002", "1.1.0", GT_ROOT)
    memory_tools = {
        "vol_pslist",
        "vol_netscan",
        "windows_psscan",
        "windows_netscan",
        "windows_mftscan",
        "windows_registry_printkey",
        "volatility_pslist",
        "volatility_netscan",
        "volatility_malfind",
    }
    for ioc in gt.iocs:
        tools = set(ioc.evidence_location)
        assert not (tools & memory_tools), (
            f"TEST-002 IOC {ioc.ioc_id} references memory tool {tools & memory_tools}; "
            f"disk case must use filesystem/MFT/registry surface"
        )


def test_paired_dataset_covers_both_surfaces():
    """Together the two cases must exercise both memory and disk forensic surfaces."""
    gt1 = load_ground_truth("TEST-001", "1.1.0", GT_ROOT)
    gt2 = load_ground_truth("TEST-002", "1.1.0", GT_ROOT)

    test001_tools = {t for ioc in gt1.iocs for t in ioc.evidence_location}
    test002_tools = {t for ioc in gt2.iocs for t in ioc.evidence_location}

    assert any("vol" in t or "psscan" in t or "netscan" in t for t in test001_tools), (
        "TEST-001 must exercise the Volatility memory surface"
    )
    assert any(
        t in {"filesystem_walk", "mft_parse", "registry_hive_parse"} for t in test002_tools
    ), "TEST-002 must exercise the disk forensic surface"
