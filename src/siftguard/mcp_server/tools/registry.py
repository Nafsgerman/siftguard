from __future__ import annotations
from siftguard.models.forensic import ForensicResult, ToolOutcome
from siftguard.mcp_server.safe_exec import safe_exec, SafeExecError

# High-value registry plugins for malware hunting
REGRIPPER_PLUGINS = [
    "autoruns",     # persistence
    "services",     # malicious services
    "run",          # run keys
    "userassist",   # executed programs
    "shellbags",    # accessed folders
    "recentdocs",   # recently opened files
    "networklist",  # connected networks
    "timezone",     # system timezone
    "samparse",     # local user accounts
]


async def run_regripper(
    *,
    hive_path: str,
    plugin: str = "autoruns",
) -> ForensicResult:
    """Run a regripper plugin against a registry hive. READ-ONLY."""
    if plugin not in REGRIPPER_PLUGINS:
        return ForensicResult(
            tool="run_regripper", outcome=ToolOutcome.FAIL,
            summary=f"plugin '{plugin}' not in approved list: {REGRIPPER_PLUGINS}",
            duration_ms=0,
            error="unapproved plugin",
        )
    try:
        result = await safe_exec(
            "rip.pl", ["-r", hive_path, "-p", plugin],
            timeout_s=120,
        )
    except SafeExecError as e:
        return ForensicResult(tool="run_regripper", outcome=ToolOutcome.FAIL,
                              summary=str(e), duration_ms=0, error=str(e))

    if result.returncode != 0:
        return ForensicResult(tool="run_regripper", outcome=ToolOutcome.FAIL,
                              summary=f"regripper plugin {plugin} failed",
                              raw_excerpt=result.stderr[:1500],
                              duration_ms=result.duration_ms,
                              error=result.stderr[:500])

    return ForensicResult(
        tool="run_regripper", outcome=ToolOutcome.OK,
        summary=f"regripper {plugin} completed on {hive_path}",
        findings=[{"plugin": plugin, "output": result.stdout[:5000]}],
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[hive_path],
        duration_ms=result.duration_ms,
    )
