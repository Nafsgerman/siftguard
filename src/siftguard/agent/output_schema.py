"""Pydantic schema for v2 structured agent output.

This is the per-iteration output schema — distinct from Trace which is
the post-run aggregated record. One AgentOutput per agent response turn.
"""
from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class FindingOutput(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_excerpt: str
    supporting_audit_entry_ids: list[int] = Field(default_factory=list)
    mitre_technique: Optional[str] = None
    reasoning: str
    training_annotation: Optional[str] = None

    @field_validator("confidence")
    @classmethod
    def confidence_floor(cls, v: float) -> float:
        if v < 0.30:
            raise ValueError(
                f"Confidence {v} is below the 0.30 reporting floor. "
                "Do not report findings below 0.30 — they are noise."
            )
        return v

    @field_validator("evidence_excerpt")
    @classmethod
    def excerpt_length(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError(
                f"evidence_excerpt too short ({len(v)} chars). Minimum 10."
            )
        if len(v) > 200:
            raise ValueError(
                f"evidence_excerpt too long ({len(v)} chars). Maximum 200."
            )
        return v


class HypothesisOutput(BaseModel):
    hypothesis_id: str
    event_type: str = Field(
        pattern="^(formed|updated|confirmed|abandoned)$"
    )
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class VerdictOutput(BaseModel):
    claim: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_finding_ids: list[str]
    reasoning: str
    mitre_techniques: list[str] = Field(default_factory=list)


class NextAction(BaseModel):
    decision: str = Field(pattern="^(continue|verdict|abort)$")
    tool_to_call: Optional[str] = None
    rationale: str


class AgentOutput(BaseModel):
    """Complete structured output from one agent response turn."""

    iteration_summary: str
    correction_event: Optional[str] = Field(
        default=None,
        pattern="^(tool_failure_recovery|hypothesis_revision|data_conflict|gap_detection)$",
    )
    findings: list[FindingOutput] = Field(default_factory=list)
    hypotheses: list[HypothesisOutput] = Field(default_factory=list)
    next_action: NextAction
    verdict: Optional[VerdictOutput] = None

    @model_validator(mode="after")
    def validate_verdict_finding_refs(self) -> "AgentOutput":
        """Ref-check runs first — guarantees aggregation validator sees valid IDs."""
        if self.verdict is None:
            return self
        finding_ids = {f.id for f in self.findings}
        for fid in self.verdict.supporting_finding_ids:
            if fid not in finding_ids:
                raise ValueError(
                    f"Verdict references finding_id '{fid}' "
                    "not present in this output's findings list."
                )
        return self

    @model_validator(mode="after")
    def validate_verdict_confidence_aggregation(self) -> "AgentOutput":
        """Verdict confidence must not exceed minimum supporting finding confidence."""
        if self.verdict is None:
            return self
        if not self.verdict.supporting_finding_ids:
            return self
        finding_map = {f.id: f.confidence for f in self.findings}
        matched = [
            finding_map[fid]
            for fid in self.verdict.supporting_finding_ids
            if fid in finding_map
        ]
        if not matched:
            return self
        min_confidence = min(matched)
        if self.verdict.confidence > min_confidence + 1e-6:
            raise ValueError(
                f"Verdict confidence {self.verdict.confidence:.3f} exceeds "
                f"minimum supporting finding confidence {min_confidence:.3f}. "
                f"Verdict confidence must be <= {min_confidence:.3f}."
            )
        return self