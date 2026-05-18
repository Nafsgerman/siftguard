"""Trace — agent-agnostic evaluation data model for SIFTGuard.

Design: docs/adr/ADR-002-trace-data-model.md
Any agent (SIFTGuard, LangGraph, OpenAI FC, Protocol SIFT) emits a Trace.
The evaluation framework consumes Traces; it never reads agent internals.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from siftguard.eval.verifier_models import VerificationResult

SCHEMA_VERSION = "1.0.0"


# ── Enums ─────────────────────────────────────────────────────────────────────


class FindingType(StrEnum):
    PROCESS = "process"
    IP = "ip"
    PORT = "port"
    TECHNIQUE = "technique"
    FILE = "file"
    REGISTRY_KEY = "registry_key"
    PERSISTENCE = "persistence"
    OTHER = "other"


class HypothesisEventType(StrEnum):
    FORMED = "formed"
    UPDATED = "updated"
    CONFIRMED = "confirmed"
    ABANDONED = "abandoned"


class Orchestrator(StrEnum):
    SIFTGUARD_NATIVE = "siftguard-native"
    LANGGRAPH = "langgraph"
    OPENAI_FC = "openai-fc"
    CLAUDE_CODE = "claude-code"
    PROTOCOL_SIFT = "protocolsift"
    CUSTOM = "custom"


class TerminatedReason(StrEnum):
    VERDICT_REACHED = "verdict_reached"
    MAX_ITERATIONS = "max_iterations"
    ERROR = "error"
    ABORTED = "aborted"


class CorrectionEvent(StrEnum):
    TOOL_FAILURE_RECOVERY = "tool_failure_recovery"
    HYPOTHESIS_REVISION = "hypothesis_revision"
    DATA_CONFLICT = "data_conflict"
    GAP_DETECTION = "gap_detection"


# ── Leaf models ───────────────────────────────────────────────────────────────


class Finding(BaseModel, frozen=True):
    """Single forensic finding. The hallucination verifier walks this list."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Stable UUID for this finding across the trace.",
    )
    type: FindingType
    value: str = Field(description="The artifact: IP, process name, port, MITRE ID, etc.")
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Agent-stated confidence [0,1]. None if agent does not emit confidence.",
    )
    supporting_audit_entry_ids: list[int] = Field(
        default_factory=list,
        description="Foreign keys into auditentry.id. Which tool calls produced this.",
    )
    evidence_excerpt: str = Field(
        description=(
            "Quoted substring from raw tool output anchoring this finding. "
            "Hallucination verifier checks: excerpt in raw_tool_output. "
            "Must be 10–200 characters."
        ),
    )
    verification: VerificationResult | None = Field(
        default=None,
        description="Result of hallucination verification. None until verifier has run.",
    )
    mitre_technique: str | None = Field(default=None)
    first_seen_iteration: int = Field(
        ge=0,
        description="Iteration in which agent first claimed this finding.",
    )

    @field_validator("evidence_excerpt")
    @classmethod
    def excerpt_length(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError(
                f"evidence_excerpt too short ({len(v)} chars). "
                "Minimum 10 chars required for verifier reliability."
            )
        if len(v) > 200:
            raise ValueError(f"evidence_excerpt too long ({len(v)} chars). Maximum 200 chars.")
        return v


Finding.model_rebuild()


class ToolCall(BaseModel, frozen=True):
    """Single tool invocation. References the audit DB row."""

    audit_entry_id: int = Field(description="Foreign key into auditentry.id.")
    tool_name: str
    iteration: int = Field(ge=0)
    outcome: str = Field(description="ok | partial | fail")
    duration_ms: int = Field(ge=0)
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    correction_event: CorrectionEvent | None = None
    finding_ids_produced: list[str] = Field(
        default_factory=list,
        description="IDs of Finding objects this tool call contributed to.",
    )


class HypothesisEvent(BaseModel, frozen=True):
    """Belief evolution event. Populates the hypothesis-evolution timeline panel."""

    run_id: str
    iteration: int = Field(ge=0)
    event_type: HypothesisEventType
    hypothesis_id: str
    content: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )


class IterationSnapshot(BaseModel, frozen=True):
    """Complete agent state at an iteration boundary."""

    run_id: str
    iteration: int = Field(ge=0)
    findings_count: int = Field(ge=0)
    iocs_count: int = Field(ge=0)
    hypotheses_count: int = Field(ge=0)
    cumulative_tokens_in: int = Field(ge=0, default=0)
    cumulative_tokens_out: int = Field(ge=0, default=0)
    cumulative_cost_usd: float = Field(ge=0.0, default=0.0)
    wall_time_ms: int = Field(ge=0)
    created_at: datetime


class Verdict(BaseModel, frozen=True):
    """Final agent verdict. Structured for the verifier and comparative panel."""

    claim: str = Field(description="Human-readable verdict statement.")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    supporting_finding_ids: list[str] = Field(
        description="IDs of Finding objects supporting this verdict.",
    )
    reasoning: str
    mitre_techniques: list[str] = Field(default_factory=list)
    terminated_reason: TerminatedReason


class ExperimentConfig(BaseModel, frozen=True):
    """Full parameterisation of a run. One dict per experiment matrix entry."""

    agent_id: str
    model: str = Field(description="e.g. claude-sonnet-4-6, gpt-4o, gemini-2.5-pro")
    orchestrator: Orchestrator = Orchestrator.SIFTGUARD_NATIVE
    self_correction: bool = True
    correlation: bool = True
    training_mode: bool = False
    max_iterations: int = Field(default=15, ge=1, le=50)
    seed: int | None = None
    prompt_version: str = Field(
        default="v1",
        description="v1 = original. v2-structured-confidence = explicit JSON confidence.",
    )
    notes: str = ""


class TraceMeta(BaseModel, frozen=True):
    """Run identity and provenance."""

    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    case_id: str
    schema_version: str = Field(default=SCHEMA_VERSION)
    started_at: datetime
    completed_at: datetime | None = None
    sift_image_sha256: str | None = Field(
        default=None,
        description=(
            "SHA-256 of the evidence image. Proves trace was run against "
            "the claimed evidence file. Populated at runtime if feasible."
        ),
    )


class UsageTotals(BaseModel, frozen=True):
    """Aggregated cost and time for the full run."""

    tokens_in: int = Field(ge=0, default=0)
    tokens_out: int = Field(ge=0, default=0)
    cost_usd: float = Field(ge=0.0, default=0.0)
    wall_time_ms: int = Field(ge=0, default=0)
    completed_iterations: int = Field(ge=0, default=0)


# ── Root model ────────────────────────────────────────────────────────────────


class Trace(BaseModel, frozen=True):
    """
    Complete agent run record. Portable, hashable, version-stamped.

    Any agent that implements a to_trace() adapter can be evaluated
    by the SIFTGuard empirical framework without modification.

    ADR: docs/adr/ADR-002-trace-data-model.md
    """

    meta: TraceMeta
    config: ExperimentConfig
    tool_calls: tuple[ToolCall, ...] = Field(default_factory=tuple)
    iterations: tuple[IterationSnapshot, ...] = Field(default_factory=tuple)
    hypothesis_events: tuple[HypothesisEvent, ...] = Field(default_factory=tuple)
    findings: tuple[Finding, ...] = Field(default_factory=tuple)
    verdict: Verdict | None = None
    usage: UsageTotals = Field(default_factory=UsageTotals)

    @model_validator(mode="after")
    def validate_schema_version(self) -> Trace:
        if self.meta.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported schema_version '{self.meta.schema_version}'. "
                f"Expected '{SCHEMA_VERSION}'. "
                "Use a version-compatible reader or migrate the trace."
            )
        return self

    @model_validator(mode="after")
    def validate_verdict_finding_refs(self) -> Trace:
        if self.verdict is None:
            return self
        finding_ids = {f.id for f in self.findings}
        for fid in self.verdict.supporting_finding_ids:
            if fid not in finding_ids:
                raise ValueError(
                    f"Verdict references finding_id '{fid}' not present in trace.findings."
                )
        return self

    def to_json(self) -> str:
        """Serialise to canonical JSON (sorted keys for stable hashing)."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, text: str) -> Trace:
        return cls.model_validate_json(text)

    def sha256(self) -> str:
        """Stable content hash for provenance. Independent of serialisation order."""
        canonical = json.dumps(json.loads(self.to_json()), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    @property
    def finding_ids(self) -> set[str]:
        return {f.id for f in self.findings}

    @property
    def ioc_findings(self) -> tuple[Finding, ...]:
        """Findings that are IOC-type (process, ip, port, technique)."""
        IOC_TYPES = {
            FindingType.PROCESS,
            FindingType.IP,
            FindingType.PORT,
            FindingType.TECHNIQUE,
        }
        return tuple(f for f in self.findings if f.type in IOC_TYPES)
