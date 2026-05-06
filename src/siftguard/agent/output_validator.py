"""v2 output validator with JSON extraction, schema validation, and retry logic.

Implements:
- JSON block extraction from agent free-text response
- Pydantic schema validation (AgentOutput)
- Verdict aggregation rule enforcement
- Single retry on failure with error feedback
- v1 fallback on second failure (Q4: v2 with v1 fallback)
"""
from __future__ import annotations

import json
import re
from typing import Optional

from siftguard.agent.output_schema import AgentOutput
from pydantic import ValidationError


_JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)


def extract_json_block(text: str) -> Optional[str]:
    """Extract first ```json ... ``` block from agent response."""
    m = _JSON_BLOCK_RE.search(text)
    return m.group(1).strip() if m else None


def parse_agent_output(text: str) -> tuple[Optional[AgentOutput], Optional[str]]:
    """
    Attempt to parse v2 structured output from agent response text.

    Returns:
        (AgentOutput, None)          — success
        (None, error_feedback_str)   — failure with feedback for retry
    """
    json_str = extract_json_block(text)
    if json_str is None:
        return None, (
            "Your response did not contain a ```json ... ``` block. "
            "Every response must end with the required JSON schema block. "
            "Reproduce your analysis and append the JSON block."
        )

    try:
        raw = json.loads(json_str)
    except json.JSONDecodeError as e:
        return None, (
            f"JSON parse error: {e}. "
            "Check for unescaped quotes, trailing commas, or missing braces."
        )

    try:
        output = AgentOutput.model_validate(raw)
        return output, None
    except ValidationError as e:
        errors = "; ".join(
            f"{' -> '.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in e.errors()
        )
        return None, (
            f"Schema validation failed: {errors}. "
            "Review the output contract in the system prompt and correct these fields."
        )


def build_retry_message(error_feedback: str) -> str:
    """Build the user-role retry message fed back to the agent."""
    return (
        f"[SCHEMA VALIDATION FAILED]\n\n"
        f"{error_feedback}\n\n"
        "Reproduce your analysis with corrected JSON. "
        "This is retry 1 of 1. A second failure will terminate this iteration."
    )


def is_v2_response(text: str) -> bool:
    """Heuristic: does this response look like a v2 structured output?"""
    return "```json" in text and '"next_action"' in text