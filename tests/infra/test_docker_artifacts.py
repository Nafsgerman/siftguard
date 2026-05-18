"""T19 infrastructure smoke tests.

Cheap structural checks — does not execute docker build. The wall-clock
5-minute gate is enforced separately by scripts/cold_clone_test.sh.
"""

# At top of file, add to imports:
from pathlib import Path
from typing import ClassVar

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(name: str) -> str:
    path = REPO_ROOT / name
    assert path.exists(), f"missing {name}"
    return path.read_text(encoding="utf-8")


class TestDockerfile:
    def test_exists(self):
        assert (REPO_ROOT / "Dockerfile").exists()

    def test_uses_slim_bookworm_base(self):
        assert "python:3.11-slim-bookworm" in _read("Dockerfile")

    def test_clones_volatility3(self):
        content = _read("Dockerfile")
        assert "volatility3.git" in content
        assert "/opt/volatility3" in content

    def test_recreates_sift_bin_path(self):
        # Source hardcodes /opt/volatility3/bin/vol — image MUST honour it.
        assert "/opt/volatility3/bin/vol" in _read("Dockerfile")

    def test_exposes_dashboard_port(self):
        assert "EXPOSE 8080" in _read("Dockerfile")

    def test_has_healthcheck(self):
        assert "HEALTHCHECK" in _read("Dockerfile")

    def test_runs_as_non_root(self):
        assert "USER siftguard" in _read("Dockerfile")

    def test_cases_volume_declared(self):
        assert 'VOLUME ["/cases"]' in _read("Dockerfile")

    def test_multi_stage(self):
        content = _read("Dockerfile")
        assert "AS deps" in content
        assert "AS runtime" in content


class TestDockerignore:
    EXPECTED: ClassVar[list[str]] = [
        "cases/",
        ".venv",
        "*.img",
        "agent_audit.db",
        "siftguard_cache/",
        ".git",
        "tests/",
    ]

    @pytest.mark.parametrize("pattern", EXPECTED)
    def test_excludes(self, pattern):
        assert pattern in _read(".dockerignore"), f".dockerignore must exclude {pattern}"


class TestMakefile:
    REQUIRED_TARGETS: ClassVar[list[str]] = [
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
    def test_target_exists(self, target):
        assert target in _read("Makefile"), f"Makefile missing target {target}"

    def test_demo_uses_port_8080(self):
        assert "8080" in _read("Makefile")

    def test_build_targets_amd64(self):
        assert "linux/amd64" in _read("Makefile")

    def test_lock_target_uses_pip_compile(self):
        assert "pip-compile" in _read("Makefile")


class TestColdCloneScript:
    SCRIPT = "scripts/cold_clone_test.sh"

    def test_exists(self):
        assert (REPO_ROOT / self.SCRIPT).exists()

    def test_shebang(self):
        first_line = _read(self.SCRIPT).splitlines()[0]
        assert first_line.startswith("#!/")

    def test_enforces_5_minute_budget(self):
        content = _read(self.SCRIPT)
        assert "BUDGET_SECONDS=300" in content

    def test_uses_make_demo(self):
        assert "make demo" in _read(self.SCRIPT)
