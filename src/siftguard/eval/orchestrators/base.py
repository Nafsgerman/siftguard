from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OrchestratorResult:
    agent_id: str
    case_id: str
    wall_time_s: float
    success: bool
    error: str | None
    raw_stdout: str
    raw_stderr: str
    report: dict[str, Any] | None
    tool_calls: int
    agent_text: str = ""


class BaseOrchestrator:
    agent_id: str = "base"

    def run(self, case_id: str, prompt: str) -> OrchestratorResult:
        raise NotImplementedError
