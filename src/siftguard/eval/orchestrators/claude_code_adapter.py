"""Claude Code orchestrator adapter for SIFTGuard Panel 7 comparison.

Invokes the `claude` CLI in headless mode against the SIFTGuard MCP server 
configured via .mcp.json. The agent reads CLAUDE.md, runs the investigation
fully autonomously, and emits a `siftguard-report` JSON block we parse out.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from siftguard.eval.orchestrators.base import BaseOrchestrator, OrchestratorResult


REPORT_BLOCK_RE = re.compile(
    r"```siftguard-report\s*\n(?P<json>.*?)\n```",
    re.DOTALL,
)

DEFAULT_CWD = Path("/cases/TEST-001/siftguard")
DEFAULT_TIMEOUT_S = 600  # 10 min wall budget, matches Panel 7 spec
DEFAULT_MODEL = "claude-sonnet-4-6"


@dataclass
class ClaudeCodeAdapter(BaseOrchestrator):
    """Headless `claude` CLI orchestrator.

    Assumes:
      - `claude` is on PATH (Claude Code CLI installed).
      - CLAUDE.md exists at `cwd`.
      - .mcp.json at `cwd` declares the siftguard MCP server.
    """

    agent_id: str = "siftguard-claudecode"
    cwd: Path = field(default_factory=lambda: DEFAULT_CWD)
    timeout_s: int = DEFAULT_TIMEOUT_S
    model: str = DEFAULT_MODEL
    extra_cli_args: list[str] = field(default_factory=list)

    def run(self, case_id: str, prompt: str) -> OrchestratorResult:
        if not (self.cwd / "CLAUDE.md").exists():
            raise FileNotFoundError(f"CLAUDE.md not found at {self.cwd}")
        if not (self.cwd / ".mcp.json").exists():
            raise FileNotFoundError(f".mcp.json not found at {self.cwd}")

        cli = [
            "claude",
            "-p", prompt,
            "--output-format", "json",
            "--model", self.model,
            "--permission-mode", "bypassPermissions",
            *self.extra_cli_args,
        ]

        env = os.environ.copy()
        env["SIFTGUARD_CASE_ID"] = case_id
        env_file = self.cwd / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env.setdefault(k.strip(), v.strip().strip('"').strip("'"))

        # Audit DB instrumentation (parity with other orchestrators)
        run_id = str(uuid.uuid4())
        audit_db = self.cwd / "audit" / f"{case_id}.db"
        snap = None
        try:
            from siftguard.agent.instrumentation import SnapshotWriter
            snap = SnapshotWriter(str(audit_db))
            snap.write_experiment_run_start(
                run_id=run_id, case_id=case_id, agent_id=self.agent_id,
                config={"model": self.model, "orchestrator": "claudecode", "cli": "headless"},
            )
        except Exception:
            snap = None

        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cli,
                cwd=str(self.cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                env=env,
                check=False,
                stdin=subprocess.DEVNULL,
            )       
        except subprocess.TimeoutExpired as exc:
            # Estimate cost from Claude CLI envelope
        cost_usd = 0.0
        tokens_in = tokens_out = 0
        try:
            env = json.loads(proc.stdout)
            cost_usd = float(env.get("total_cost_usd", 0) or 0)
            usage = env.get("usage", {}) or {}
            tokens_in  = int(usage.get("input_tokens", 0) or 0)
            tokens_out = int(usage.get("output_tokens", 0) or 0)
        except Exception:
            pass

        if snap:
            try:
                snap.write_experiment_run_complete(
                    run_id=run_id,
                    completed_iterations=tool_calls,
                    terminated_reason="verdict_reached" if report else "error",
                    total_tokens_in=tokens_in,
                    total_tokens_out=tokens_out,
                    total_cost_usd=cost_usd,
                    final_score=None,
                )
            except Exception:
                pass

        return OrchestratorResult(
            agent_id=self.agent_id,
            case_id=case_id,
            wall_time_s=wall,
            success=report is not None,
            error=None if report is not None else "no siftguard-report block found",
            raw_stdout=proc.stdout,
            raw_stderr=proc.stderr,
            report=report,
            tool_calls=tool_calls,
            agent_text=agent_text,
        )

        wall = time.monotonic() - t0

        if proc.returncode != 0:
            return OrchestratorResult(
                agent_id=self.agent_id,
                case_id=case_id,
                wall_time_s=wall,
                success=False,
                error=f"exit={proc.returncode}",
                raw_stdout=proc.stdout,
                raw_stderr=proc.stderr,
                report=None,
                tool_calls=0,
            )

        report, tool_calls, agent_text = self._parse_output(proc.stdout)

        return OrchestratorResult(
            agent_id=self.agent_id,
            case_id=case_id,
            wall_time_s=wall,
            success=report is not None,
            error=None if report is not None else "no siftguard-report block found",
            raw_stdout=proc.stdout,
            raw_stderr=proc.stderr,
            report=report,
            tool_calls=tool_calls,
            agent_text=agent_text,
        )

    @staticmethod
    def _parse_output(stdout: str) -> tuple[dict[str, Any] | None, int, str]:
        """Extract the siftguard-report JSON, tool-call count, and final text.

        Claude Code --output-format=json emits a single JSON envelope with
        keys: result (final assistant text), num_turns, total_cost_usd, ...
        """
        try:
            envelope = json.loads(stdout)
            final_text = envelope.get("result") or ""
            tool_calls = int(envelope.get("num_turns", 0))
        except json.JSONDecodeError:
            # Fall back to raw stdout (older CLI versions or streaming mode).
            final_text = stdout
            tool_calls = stdout.count('"type":"tool_use"')

        match = REPORT_BLOCK_RE.search(final_text)
        if not match:
            return None, tool_calls, final_text

        try:
            report = json.loads(match.group("json"))
        except json.JSONDecodeError:
            return None, tool_calls, final_text

        return report, tool_calls, final_text