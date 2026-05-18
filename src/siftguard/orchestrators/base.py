from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BaseOrchestrator(Protocol):
    """Contract every orchestrator satisfies."""

    name: str

    async def run_case(
        self,
        case_id: str,
        evidence_files: dict[str, str],
        briefing: str,
        audit_db: str,
        training_mode: bool,
        model: str,
        config_override: dict | None,
        ground_truth_path: str | None,
        on_event: Callable[..., Any] | None,
    ) -> tuple[str, str]:
        """Returns (final_report, run_id)."""
        ...
