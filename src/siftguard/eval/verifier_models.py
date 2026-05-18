from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class VerificationMethod(StrEnum):
    SUBSTRING_MATCH = "substring_match"
    TOOL_RERUN = "tool_rerun"
    UNVERIFIABLE = "unverifiable"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    REFUTED = "refuted"
    UNVERIFIABLE = "unverifiable"


class VerificationResult(BaseModel):
    finding_id: str
    status: VerificationStatus
    method: VerificationMethod
    confidence: float = Field(ge=0.0, le=1.0)
    matched_evidence: str | None = None
    refutation_reason: str | None = None
    tool_output_snippet: str | None = None
