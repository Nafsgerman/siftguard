from enum import StrEnum

from pydantic import BaseModel


class SelfCorrectionType(StrEnum):
    FORMAT_RETRY = "FORMAT_RETRY"
    TOOL_RETRY = "TOOL_RETRY"
    VERDICT_REVISION = "VERDICT_REVISION"
    IOC_REVISION = "IOC_REVISION"
    SECTION_REFILL = "SECTION_REFILL"
    HALLUCINATION_RETRACT = "HALLUCINATION_RETRACT"
    CONFIDENCE_DOWNGRADE = "CONFIDENCE_DOWNGRADE"
    SCOPE_EXPANSION = "SCOPE_EXPANSION"
    UNKNOWN = "UNKNOWN"


class SelfCorrectionEvent(BaseModel):
    audit_id: int
    event_type: SelfCorrectionType
    original_value: str | None = None
    corrected_value: str | None = None
    iteration: int
    tool_name: str | None = None
    message: str


_CLASSIFIER_RULES: list[tuple[SelfCorrectionType, list[str]]] = [
    (
        SelfCorrectionType.FORMAT_RETRY,
        ["validation error", "pydantic", "schema mismatch", "invalid json", "parse error"],
    ),
    (
        SelfCorrectionType.HALLUCINATION_RETRACT,
        ["retract", "unverifiable", "cannot confirm", "no evidence", "hallucin"],
    ),
    (
        SelfCorrectionType.VERDICT_REVISION,
        ["verdict changed", "verdict revised", "updated verdict", "revising verdict"],
    ),
    (SelfCorrectionType.IOC_REVISION, ["ioc", "indicator", "ip address", "domain", "hash", "port"]),
    (
        SelfCorrectionType.SECTION_REFILL,
        ["section empty", "refill", "re-ran section", "empty result", "retrying section"],
    ),
    (
        SelfCorrectionType.TOOL_RETRY,
        [
            "tool error",
            "tool failed",
            "volatility error",
            "command failed",
            "retry tool",
            "subprocess",
        ],
    ),
    (
        SelfCorrectionType.CONFIDENCE_DOWNGRADE,
        ["confidence", "downgrade", "lowered score", "reducing confidence"],
    ),
    (
        SelfCorrectionType.SCOPE_EXPANSION,
        ["expanding scope", "additional artifact", "new lead", "pivot to"],
    ),
]


def classify_correction(message: str) -> SelfCorrectionType:
    lowered = message.lower()
    for event_type, keywords in _CLASSIFIER_RULES:
        if any(kw in lowered for kw in keywords):
            return event_type
    return SelfCorrectionType.UNKNOWN
