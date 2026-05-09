from __future__ import annotations
import json
import os
from pathlib import Path
from pydantic import BaseModel

CASES_ROOT = Path(os.environ.get("SIFTGUARD_CASES_ROOT", "/cases"))
GT_DIR = Path(__file__).resolve().parents[4] / "tests" / "benchmark" / "ground_truth"

class DatasetMeta(BaseModel):
    case_id: str
    description: str
    threat_type: str
    memory_image: Path
    ground_truth_path: Path
    briefing: str
    model_config = {"frozen": True}

    @property
    def evidence_available(self) -> bool:
        return self.memory_image.exists()

    @property
    def ground_truth_available(self) -> bool:
        return self.ground_truth_path.exists()

    def load_ground_truth(self) -> dict:
        return json.loads(self.ground_truth_path.read_text())

    def to_evidence_dict(self) -> dict[str, str]:
        return {"memory": str(self.memory_image)}

_REGISTRY: dict[str, DatasetMeta] = {
    "TEST-001": DatasetMeta(case_id="TEST-001", description="SRL-2018 APT hunt scenario. C2 at 172.16.4.10:8080, backdoors on 5682/33001.", threat_type="apt_c2", memory_image=CASES_ROOT/"TEST-001"/"base-hunt-memory.img", ground_truth_path=GT_DIR/"TEST-001.json", briefing="Windows 10 x64 memory image from SRL-2018 APT hunt scenario. Suspected compromise with C2 activity. Find evil."),
    "TEST-004": DatasetMeta(case_id="TEST-004", description="Windows 10 x64. Registry persistence, truncated process names.", threat_type="apt_persistence_registry", memory_image=CASES_ROOT/"TEST-004"/"base-hunt-memory.img", ground_truth_path=GT_DIR/"TEST-004.json", briefing="Windows 10 x64 memory image. Focus: registry persistence and truncated process names."),
    "TEST-005": DatasetMeta(case_id="TEST-005", description="Windows 10 x64. Full C2 infrastructure mapping, lateral movement.", threat_type="apt_c2_full", memory_image=CASES_ROOT/"TEST-005"/"base-hunt-memory.img", ground_truth_path=GT_DIR/"TEST-005.json", briefing="Windows 10 x64 memory image. Focus: full C2 infrastructure mapping and network correlation."),
}

def get_dataset(case_id: str) -> DatasetMeta:
    if case_id not in _REGISTRY:
        raise KeyError(f"Unknown case_id: {case_id!r}. Available: {list(_REGISTRY)}")
    return _REGISTRY[case_id]

def list_datasets() -> list[str]:
    return list(_REGISTRY)

def available_datasets() -> list[str]:
    return [cid for cid, meta in _REGISTRY.items() if meta.evidence_available and meta.ground_truth_available]
