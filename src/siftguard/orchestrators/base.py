from __future__ import annotations
from typing import Optional, Protocol, runtime_checkable


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
        config_override: Optional[dict],
        ground_truth_path: Optional[str],
        on_event: Optional[callable],
    ) -> tuple[str, str]:
        """Returns (final_report, run_id)."""
        ...