"""SIFTGuard evaluation framework — agent-agnostic trace-based evaluation."""

from siftguard.eval.trace import (
    SCHEMA_VERSION,
    CorrectionEvent,
    ExperimentConfig,
    Finding,
    FindingType,
    HypothesisEvent,
    HypothesisEventType,
    IterationSnapshot,
    Orchestrator,
    TerminatedReason,
    ToolCall,
    Trace,
    TraceMeta,
    UsageTotals,
    Verdict,
)

__all__ = [
    "CorrectionEvent",
    "ExperimentConfig",
    "Finding",
    "FindingType",
    "HypothesisEvent",
    "HypothesisEventType",
    "IterationSnapshot",
    "Orchestrator",
    "TerminatedReason",
    "Trace",
    "TraceMeta",
    "ToolCall",
    "UsageTotals",
    "Verdict",
    "SCHEMA_VERSION",
]
