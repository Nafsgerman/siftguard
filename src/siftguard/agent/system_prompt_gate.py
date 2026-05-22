"""Behavioral system-prompt gate for the self-correction ablation toggle."""

from __future__ import annotations

SELF_CORRECTION_OFF_PREFIX = (
    "SELF-CORRECTION DISABLED: If a tool returns outcome=fail or raises an error, "
    "do not retry and do not substitute an alternative tool for the same goal. "
    "Record the failure in your findings and proceed to a final verdict with reduced confidence.\n\n"
)


def build_system_prompt_prefix(self_correction: bool, tool_preamble: str = "") -> str:
    """Compose the system-prompt prefix for the given ablation state.

    Order: behavioral gate (if OFF) + tool preamble.
    ON  → empty gate, preamble only (current behavior, no change).
    OFF → gate prefix prepended, preamble after.
    """
    gate = "" if self_correction else SELF_CORRECTION_OFF_PREFIX
    return gate + tool_preamble
