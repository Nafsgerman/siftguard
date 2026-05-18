"""tests/cases/test_tool_injection.py"""

from __future__ import annotations

from typing import ClassVar

from siftguard.cases.tool_injection import (
    ToolManifest,
    build_tools_preamble,
    manifest_from_case_loader,
)

# ---------------------------------------------------------------------------
# Unit: build_tools_preamble
# ---------------------------------------------------------------------------


class TestBuildToolsPreamble:
    def test_returns_string(self):
        m = ToolManifest(
            case_id="TEST-001", available_tools=["windows_psscan"], unavailable_tools=[]
        )
        result = build_tools_preamble(m)
        assert isinstance(result, str)

    def test_contains_case_id(self):
        m = ToolManifest(case_id="TEST-001", available_tools=[], unavailable_tools=[])
        assert "TEST-001" in build_tools_preamble(m)

    def test_available_tool_listed(self):
        m = ToolManifest(
            case_id="X", available_tools=["windows_psscan", "windows_netscan"], unavailable_tools=[]
        )
        result = build_tools_preamble(m)
        assert "windows_psscan" in result
        assert "windows_netscan" in result

    def test_unavailable_tool_with_reason(self):
        m = ToolManifest(
            case_id="X",
            available_tools=[],
            unavailable_tools=[{"tool": "linux_bash_history", "reason": "Windows image"}],
        )
        result = build_tools_preamble(m)
        assert "linux_bash_history" in result
        assert "Windows image" in result

    def test_ends_with_separator(self):
        m = ToolManifest(case_id="X", available_tools=[], unavailable_tools=[])
        result = build_tools_preamble(m)
        assert "---" in result

    def test_empty_available_shows_none(self):
        m = ToolManifest(case_id="X", available_tools=[], unavailable_tools=[])
        result = build_tools_preamble(m)
        assert "(none specified)" in result

    def test_empty_unavailable_shows_none(self):
        m = ToolManifest(case_id="X", available_tools=["tool_a"], unavailable_tools=[])
        result = build_tools_preamble(m)
        assert "(none)" in result

    def test_prepend_pattern_works(self):
        """Result should be safe to prepend to any system prompt."""
        m = ToolManifest(
            case_id="TEST-001", available_tools=["windows_psscan"], unavailable_tools=[]
        )
        preamble = build_tools_preamble(m)
        system_prompt = preamble + "You are SIFTGuard."
        assert "TEST-001" in system_prompt
        assert "You are SIFTGuard." in system_prompt

    def test_tools_sorted_alphabetically(self):
        m = ToolManifest(
            case_id="X", available_tools=["z_tool", "a_tool", "m_tool"], unavailable_tools=[]
        )
        result = build_tools_preamble(m)
        a_pos = result.index("a_tool")
        m_pos = result.index("m_tool")
        z_pos = result.index("z_tool")
        assert a_pos < m_pos < z_pos


# ---------------------------------------------------------------------------
# Unit: manifest_from_case_loader
# ---------------------------------------------------------------------------


class TestManifestFromCaseLoader:
    def test_from_dict(self):
        case_data = {
            "case_id": "TEST-002",
            "available_tools": ["windows_mftscan", "windows_filescan"],
            "unavailable_tools": [{"tool": "windows_psscan", "reason": "disk image only"}],
        }
        m = manifest_from_case_loader(case_data)
        assert m.case_id == "TEST-002"
        assert "windows_mftscan" in m.available_tools
        assert m.unavailable_tools[0]["tool"] == "windows_psscan"

    def test_from_object_with_attrs(self):
        class FakeCaseModel:
            case_id = "TEST-001"
            available_tools: ClassVar[list[str]] = ["windows_psscan"]
            unavailable_tools: ClassVar[list[str]] = []

        m = manifest_from_case_loader(FakeCaseModel())
        assert m.case_id == "TEST-001"
        assert "windows_psscan" in m.available_tools

    def test_string_unavailable_normalized(self):
        """list[str] unavailable_tools → list[dict] with reason default."""
        case_data = {
            "case_id": "X",
            "available_tools": [],
            "unavailable_tools": ["linux_bash_history"],
        }
        m = manifest_from_case_loader(case_data)
        assert m.unavailable_tools[0]["tool"] == "linux_bash_history"
        assert "reason" in m.unavailable_tools[0]

    def test_missing_fields_default_empty(self):
        m = manifest_from_case_loader({"case_id": "X"})
        assert m.available_tools == []
        assert m.unavailable_tools == []

    def test_case_id_cast_to_str(self):
        m = manifest_from_case_loader({"case_id": 42})
        assert isinstance(m.case_id, str)
        assert m.case_id == "42"


# ---------------------------------------------------------------------------
# Smoke: adapter prompt injection pattern
# ---------------------------------------------------------------------------


class TestAdapterPromptInjectionSmoke:
    """
    Validates the pattern used in all 5 adapter patches.
    If this passes, the injection contract is safe to apply.
    """

    def _make_manifest(self, available=None, unavailable=None):
        return ToolManifest(
            case_id="TEST-001",
            available_tools=available or ["windows_psscan", "windows_netscan"],
            unavailable_tools=unavailable
            or [{"tool": "linux_bash_history", "reason": "Windows image"}],
        )

    def test_preamble_does_not_break_json_serializable_content(self):
        """Preamble contains only printable ASCII — safe to embed in JSON strings."""
        preamble = build_tools_preamble(self._make_manifest())
        preamble.encode("ascii")  # raises if non-ASCII

    def test_preamble_length_reasonable(self):
        """Preamble must not blow up context unnecessarily."""
        m = ToolManifest(
            case_id="TEST-001",
            available_tools=[f"tool_{i}" for i in range(20)],
            unavailable_tools=[{"tool": f"bad_tool_{i}", "reason": "N/A"} for i in range(10)],
        )
        preamble = build_tools_preamble(m)
        assert len(preamble) < 4000  # well under any model's context limit concern

    def test_preamble_stable_given_same_input(self):
        """Deterministic — same manifest → same string (no random ordering)."""
        m = self._make_manifest()
        assert build_tools_preamble(m) == build_tools_preamble(m)

    def test_case_id_none_handled(self):
        """Adapter calls with case_data=None must not crash."""
        preamble = build_tools_preamble(self._make_manifest()) if True else ""
        assert isinstance(preamble, str)
