from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class VerificationMethod(str, Enum):
    SUBSTRING_MATCH = "substring_match"
    TOOL_RERUN = "tool_rerun"
    UNVERIFIABLE = "unverifiable"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    REFUTED = "refuted"
    UNVERIFIABLE = "unverifiable"


class VerificationResult(BaseModel):
    finding_id: str
    status: VerificationStatus
    method: VerificationMethod
    confidence: float = Field(ge=0.0, le=1.0)
    matched_evidence: Optional[str] = None
    refutation_reason: Optional[str] = None
    tool_output_snippet: Optional[str] = None