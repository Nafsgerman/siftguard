from __future__ import annotations

import json

from siftguard.mcp_server.safe_exec import SafeExecError, safe_exec
from siftguard.models.forensic import ForensicResult, ToolOutcome

VOL3 = "/opt/volatility3/bin/vol"
RIP = "/usr/local/bin/rip.pl"

REGRIPPER_PLUGINS = [
    "autoruns",
    "services",
    "run",
    "userassist",
    "shellbags",
    "recentdocs",
    "networklist",
    "timezone",
    "samparse",
]

# High-value registry keys for persistence hunting — queried via printkey
PERSISTENCE_KEYS = [
    "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
    "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\RunOnce",
    "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon",
    "SYSTEM\\CurrentControlSet\\Services",
    "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Image File Execution Options",
    "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders",
]


async def list_registry_hives(*, memory_image: str) -> ForensicResult:
    """List all registry hives in memory image via Volatility3. READ-ONLY."""
    try:
        result = await safe_exec(
            VOL3,
            ["-q", "-f", memory_image, "-r", "json", "windows.registry.hivelist"],
            timeout_s=120,
        )
    except SafeExecError as e:
        return ForensicResult(
            tool="list_registry_hives",
            outcome=ToolOutcome.FAIL,
            summary=str(e),
            duration_ms=0,
            error=str(e),
        )

    if result.returncode != 0:
        return ForensicResult(
            tool="list_registry_hives",
            outcome=ToolOutcome.FAIL,
            summary="hivelist failed",
            raw_excerpt=result.stderr[:1500],
            duration_ms=result.duration_ms,
            error=result.stderr[:500],
        )

    hives = []
    try:
        raw = json.loads(result.stdout)
        for h in raw:
            name = h.get("Name") or h.get("name") or ""
            offset = h.get("Offset") or h.get("offset") or 0
            hives.append({"name": name, "offset": offset})
    except Exception:
        pass

    return ForensicResult(
        tool="list_registry_hives",
        outcome=ToolOutcome.OK,
        summary=f"{len(hives)} registry hives found in memory",
        findings=hives,
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[memory_image],
        duration_ms=result.duration_ms,
    )


async def query_registry_key(*, memory_image: str, key: str) -> ForensicResult:
    """Query a registry key directly from memory via Volatility3 printkey. READ-ONLY."""
    try:
        result = await safe_exec(
            VOL3,
            ["-q", "-f", memory_image, "-r", "json", "windows.registry.printkey", "--key", key],
            timeout_s=120,
        )
    except SafeExecError as e:
        return ForensicResult(
            tool="query_registry_key",
            outcome=ToolOutcome.FAIL,
            summary=str(e),
            duration_ms=0,
            error=str(e),
        )

    if result.returncode != 0:
        return ForensicResult(
            tool="query_registry_key",
            outcome=ToolOutcome.FAIL,
            summary=f"printkey failed for {key}",
            raw_excerpt=result.stderr[:1500],
            duration_ms=result.duration_ms,
            error=result.stderr[:500],
        )

    findings = []
    try:
        raw = json.loads(result.stdout)
        for entry in raw:
            findings.append(
                {
                    "key": key,
                    "name": entry.get("Name") or entry.get("name") or "",
                    "type": entry.get("Type") or entry.get("type") or "",
                    "data": entry.get("Data") or entry.get("data") or "",
                    "volatile": entry.get("Volatile") or False,
                }
            )
    except Exception:
        findings = [{"key": key, "raw": result.stdout[:2000]}]

    return ForensicResult(
        tool="query_registry_key",
        outcome=ToolOutcome.OK,
        summary=f"{len(findings)} values under {key}",
        findings=findings,
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[memory_image],
        duration_ms=result.duration_ms,
    )


async def run_regripper(*, hive_path: str, plugin: str = "autoruns") -> ForensicResult:
    """Run a regripper plugin against a registry hive. READ-ONLY."""
    if plugin not in REGRIPPER_PLUGINS:
        return ForensicResult(
            tool="run_regripper",
            outcome=ToolOutcome.FAIL,
            summary=f"plugin '{plugin}' not in approved list",
            duration_ms=0,
            error="unapproved plugin",
        )
    try:
        result = await safe_exec(RIP, ["-r", hive_path, "-p", plugin], timeout_s=120)
    except SafeExecError as e:
        return ForensicResult(
            tool="run_regripper",
            outcome=ToolOutcome.FAIL,
            summary=str(e),
            duration_ms=0,
            error=str(e),
        )

    if result.returncode != 0:
        return ForensicResult(
            tool="run_regripper",
            outcome=ToolOutcome.FAIL,
            summary=f"regripper {plugin} failed",
            raw_excerpt=result.stderr[:1500],
            duration_ms=result.duration_ms,
            error=result.stderr[:500],
        )

    findings = _parse_regripper_output(plugin, result.stdout)
    return ForensicResult(
        tool="run_regripper",
        outcome=ToolOutcome.OK,
        summary=f"regripper {plugin}: {len(findings)} entries",
        findings=findings,
        raw_excerpt=result.stdout[:2000],
        evidence_refs=[hive_path],
        duration_ms=result.duration_ms,
    )


async def hunt_registry(*, memory_image: str) -> ForensicResult:
    """Hunt persistence keys directly from memory via printkey. READ-ONLY."""
    all_findings = []
    total_ms = 0

    for key in PERSISTENCE_KEYS:
        r = await query_registry_key(memory_image=memory_image, key=key)
        total_ms += r.duration_ms
        if r.outcome == ToolOutcome.OK and r.findings:
            all_findings.extend(r.findings)

    return ForensicResult(
        tool="hunt_registry",
        outcome=ToolOutcome.OK,
        summary=f"registry hunt complete: {len(all_findings)} persistence findings across {len(PERSISTENCE_KEYS)} keys",
        findings=all_findings[:200],
        evidence_refs=[memory_image],
        duration_ms=total_ms,
    )


def _parse_regripper_output(plugin: str, output: str) -> list[dict]:
    findings = []
    lines = output.splitlines()
    if plugin in ("autoruns", "run"):
        for line in lines:
            line = line.strip()
            if (
                line
                and not line.startswith("#")
                and any(c in line for c in ["\\", ".exe", ".dll", ".bat", ".cmd", ".ps1"])
            ):
                findings.append({"type": "autorun_entry", "value": line})
    elif plugin == "services":
        current: dict = {}
        for line in lines:
            if line.startswith("ServiceName"):
                if current:
                    findings.append(current)
                current = {"type": "service", "name": line.split(":", 1)[-1].strip()}
            elif line.startswith("ImagePath") and current:
                current["image_path"] = line.split(":", 1)[-1].strip()
            elif line.startswith("Start") and current:
                current["start_type"] = line.split(":", 1)[-1].strip()
        if current:
            findings.append(current)
    elif plugin == "samparse":
        for line in lines:
            if any(k in line for k in ("Username", "Last Login", "Pwd", "Account")):
                findings.append({"type": "user_account", "value": line.strip()})
    else:
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and len(line) > 10:
                findings.append({"type": plugin, "value": line})
    return findings[:50]
