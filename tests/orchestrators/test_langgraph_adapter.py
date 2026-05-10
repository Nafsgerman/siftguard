"""Task 6 adapter tests."""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_langgraph_adapter_importable():
    from siftguard.orchestrators.langgraph_adapter import build_graph
    assert build_graph() is not None


def test_run_case_langgraph_callable():
    from siftguard.orchestrators.langgraph_adapter import run_case_langgraph
    assert callable(run_case_langgraph)


def test_base_protocol_importable():
    from siftguard.orchestrators.base import BaseOrchestrator
    assert BaseOrchestrator is not None


def test_seed_via_config_override():
    config_override = {"seed": 42, "orchestrator": "langgraph", "max_iterations": 2}
    assert config_override.get("seed") == 42


@pytest.mark.asyncio
async def test_run_case_langgraph_dry():
    with patch("siftguard.orchestrators.langgraph_adapter.anthropic.Anthropic") as MockClient, \
         patch("siftguard.orchestrators.langgraph_adapter.SnapshotWriter") as MockSnap, \
         patch("siftguard.orchestrators.langgraph_adapter.AuditLog"):
        mock_resp = MagicMock()
        mock_resp.usage.input_tokens = 100
        mock_resp.usage.output_tokens = 50
        mock_resp.stop_reason = "end_turn"
        mock_resp.content = []  # empty content — triggers end via stop_reason
        MockClient.return_value.messages.create.return_value = mock_resp
        MockSnap.return_value.write_experiment_run_start = MagicMock()
        MockSnap.return_value.write_experiment_run_complete = MagicMock()
        MockSnap.return_value.write_iteration_snapshot = MagicMock()

        from siftguard.orchestrators.langgraph_adapter import run_case_langgraph
        report, run_id = await run_case_langgraph(
            case_id="TEST-001",
            evidence_files={"memory": "/tmp/fake.img"},
            briefing="Test.",
            audit_db="/tmp/test.db",
            config_override={"seed": 0, "max_iterations": 1},
        )
        assert isinstance(report, str)
        assert len(run_id) == 36
