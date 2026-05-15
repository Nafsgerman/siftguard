from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field

class EvidenceLocation(str, Enum):
    MEMORY_ONLY = "memory_only"
    DISK_ONLY = "disk_only"
    BOTH = "both"

class IOCExpectation(BaseModel):
    ioc_id: str = Field(..., pattern=r"^ioc-[a-z]+-[a-z0-9-]+$")
    ioc_type: Literal["process", "network_connection", "file", "registry_key", "service", "handle"]
    expected: dict
    confidence_threshold: float = Field(..., ge=0.0, le=1.0)
    evidence_location: EvidenceLocation
    rationale: str

class GroundTruth(BaseModel):
    schema_version: Literal["1.1.0"]
    case_id: str
    iocs: list[IOCExpectation]

class ToolAvailability(BaseModel):
    tool: str
    reason: Literal["no_memory_image", "no_disk_image", "no_registry_hives", "unsupported_filesystem"]

class CaseManifest(BaseModel):
    schema_version: Literal["1.0.0"]
    case_id: str
    case_name: str
    evidence_files: list[dict]
    available_tools: list[str]
    unavailable_tools: list[ToolAvailability]
    ground_truth_path: str
    briefing: str = ""
    threat_type: str = "unknown"
    description: str = ""

    def is_tool_available(self, tool: str) -> bool:
        return tool in self.available_tools

    def reachable(self, ioc: IOCExpectation) -> bool:
        if ioc.evidence_location == EvidenceLocation.MEMORY_ONLY:
            return any(t.startswith("volatility_") for t in self.available_tools)
        if ioc.evidence_location == EvidenceLocation.DISK_ONLY:
            return any(t in self.available_tools for t in ("mft_parse", "registry_hive_parse", "filesystem_walk"))
        return True  # BOTH — reachable if any surface is available