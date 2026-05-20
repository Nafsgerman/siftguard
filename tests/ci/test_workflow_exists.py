"""Guard: CI workflow file must exist and define required jobs."""

from pathlib import Path

import pytest

WORKFLOW = Path(__file__).parent.parent.parent / ".github" / "workflows" / "ci.yml"


@pytest.fixture(scope="module")
def text() -> str:
    assert WORKFLOW.exists(), f"ci.yml missing at {WORKFLOW}"
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_exists(text: str) -> None:
    assert len(text) > 0


def test_required_jobs_present(text: str) -> None:
    for job in ("test:", "spoliation:", "docs:", "benchmark:"):
        assert job in text, f"CI job missing: {job}"


def test_python_version_pinned(text: str) -> None:
    assert "3.11" in text


def test_no_api_keys_in_workflow(text: str) -> None:
    for secret in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        assert secret not in text, f"Live API key reference found in CI: {secret}"


def test_spoliation_job_isolated(text: str) -> None:
    assert "tests/spoliation/" in text


def test_benchmark_zero_cost_scripts(text: str) -> None:
    assert "t13_score_all.py" in text
    assert "score_test002.py" in text
