"""
Tool injection helper for Lock C (T12, phase 1).
Prepends available/unavailable tool context to each orchestrator's system prompt.
MCP-level enforcement deferred to T15 + ADR-007.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolManifest:
    """Minimal manifest contract consumed by build_tools_preamble."""

    available_tools: list[str]
    unavailable_tools: list[dict[str, str]]  # [{tool: str, reason: str}]
    case_id: str


def build_tools_preamble(manifest: ToolManifest) -> str:
    """
    Returns a markdown block to prepend to every orchestrator's system prompt.
    Tells the agent which tools are safe to call and which are out of scope.

    Args:
        manifest: ToolManifest with available_tools and unavailable_tools for the case.

    Returns:
        Formatted string ready to prepend to system_prompt.
    """
    lines: list[str] = [
        f"## Tool Availability for Case {manifest.case_id}",
        "",
        "### Available tools (call freely):",
    ]
    if manifest.available_tools:
        for tool in sorted(manifest.available_tools):
            lines.append(f"- `{tool}`")
    else:
        lines.append("- (none specified)")

    lines += [
        "",
        "### Unavailable tools (do NOT call -- will error or return no data):",
    ]
    if manifest.unavailable_tools:
        for entry in manifest.unavailable_tools:
            tool = entry.get("tool", entry.get("name", "unknown"))
            reason = entry.get("reason", "not applicable for this case")
            lines.append(f"- `{tool}` -- {reason}")
    else:
        lines.append("- (none)")

    lines += [
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def manifest_from_case_loader(case_data: Any) -> ToolManifest:
    """
    Build a ToolManifest from whatever the cases/loader.py returns.
    Handles both dict and object (Pydantic model) case representations.
    """

    def _get(obj: Any, *keys: str, default: Any = None) -> Any:
        for key in keys:
            try:
                val = getattr(obj, key, None)
                if val is not None:
                    return val
            except Exception:
                pass
            try:
                val = obj[key]
                if val is not None:
                    return val
            except Exception:
                pass
        return default

    case_id = _get(case_data, "case_id", "id", default="UNKNOWN")
    available = _get(case_data, "available_tools", "tools", default=[])
    unavailable = _get(case_data, "unavailable_tools", "excluded_tools", default=[])

    # Normalise unavailable entries — accept list[str] or list[dict]
    normalised_unavailable: list[dict[str, str]] = []
    for entry in unavailable:
        if isinstance(entry, str):
            normalised_unavailable.append({"tool": entry, "reason": "not applicable for this case"})
        elif isinstance(entry, dict):
            normalised_unavailable.append(entry)

    return ToolManifest(
        case_id=str(case_id),
        available_tools=[str(t) for t in available],
        unavailable_tools=normalised_unavailable,
    )
