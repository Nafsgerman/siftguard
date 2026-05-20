"""T19: Verify Dockerfile, .dockerignore, Makefile, and cold-clone script exist
and contain required directives. No Docker daemon required."""

from __future__ import annotations

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text()


class TestDockerfile:
    def test_exists(self) -> None:
        assert (REPO_ROOT / "Dockerfile").exists()

    def test_volatility3_path(self) -> None:
        assert "/opt/volatility3/bin/vol" in _read("Dockerfile")

    def test_exposes_dashboard_port(self) -> None:
        assert "EXPOSE 8080" in _read("Dockerfile")

    def test_has_healthcheck(self) -> None:
        assert "HEALTHCHECK" in _read("Dockerfile")

    def test_runs_as_non_root(self) -> None:
        assert "USER siftguard" in _read("Dockerfile")

    def test_cases_volume_declared(self) -> None:
        assert 'VOLUME ["/cases"]' in _read("Dockerfile")

    def test_multi_stage(self) -> None:
        content = _read("Dockerfile")
        assert "AS deps" in content
        assert "AS runtime" in content


class TestDockerignore:
    EXPECTED = [
        "cases/",
        ".venv",
        "*.img",
        "agent_audit.db",
        "siftguard_cache/",
        ".git",
        "tests/",
    ]

    @pytest.mark.parametrize("pattern", EXPECTED)
    def test_excludes(self, pattern: str) -> None:
        assert pattern in _read(".dockerignore"), f".dockerignore must exclude {pattern}"


class TestMakefile:
    REQUIRED_TARGETS = [
        "build:",
        "demo:",
        "demo-stop:",
        "test:",
        "lint:",
        "type:",
        "lock:",
        "clean:",
    ]

    @pytest.mark.parametrize("target", REQUIRED_TARGETS)
    def test_target_exists(self, target: str) -> None:
        assert target in _read("Makefile"), f"Makefile missing target {target}"

    def test_demo_uses_port_8080(self) -> None:
        assert "8080" in _read("Makefile")

    def test_build_targets_amd64(self) -> None:
        assert "linux/amd64" in _read("Makefile")

    def test_lock_target_uses_pip_compile(self) -> None:
        assert "pip-compile" in _read("Makefile")


class TestColdCloneScript:
    SCRIPT = "scripts/cold_clone_test.sh"

    def test_exists(self) -> None:
        assert (REPO_ROOT / self.SCRIPT).exists()

    def test_shebang(self) -> None:
        first_line = _read(self.SCRIPT).splitlines()[0]
        assert first_line.startswith("#!/")

    def test_enforces_5_minute_budget(self) -> None:
        assert "BUDGET_SECONDS=300" in _read(self.SCRIPT)

    def test_uses_make_demo(self) -> None:
        assert "make demo" in _read(self.SCRIPT)
