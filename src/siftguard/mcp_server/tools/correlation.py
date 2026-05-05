from __future__ import annotations
import json
from siftguard.models.forensic import ForensicResult, ToolOutcome
from siftguard.mcp_server.safe_exec import safe_exec, SafeExecError

VOL3 = "/opt/volatility3/bin/vol"


async def _run_vol(memory_image: str, plugin: str) -> tuple[list[dict], int]:
    """Run a Volatility plugin and return (parsed_rows, duration_ms)."""
    result = await safe_exec(
        VOL3,
        ["-q", "-f", memory_image, "-r", "json", plugin],
        timeout_s=180,
    )
    duration = result.duration_ms
    if result.returncode != 0:
        return [], duration
    try:
        rows = json.loads(result.stdout)
        return rows, duration
    except Exception:
        return [], duration


async def correlate_findings(*, memory_image: str) -> ForensicResult:
    """
    Cross-correlate memory artifacts to detect rootkit indicators.

    Checks performed:
    1. DKOM detection — processes in psscan but hidden from pslist
    2. Orphaned connections — network connections whose PID has no matching process
    3. Truncated process names — names ending in '.e' (MFT name length artifact)
    4. Wow64 anomalies — 32-bit processes in unexpected locations
    READ-ONLY.
    """
    total_ms = 0
    findings = []
    anomalies = []

    # ── 1. Fetch pslist and psscan ────────────────────────────────────────────
    pslist_rows, ms = await _run_vol(memory_image, "windows.pslist.PsList")
    total_ms += ms
    psscan_rows, ms = await _run_vol(memory_image, "windows.psscan.PsScan")
    total_ms += ms

    pslist_pids = {
        int(r.get("PID") or 0)
        for r in pslist_rows if r.get("PID")
    }
    psscan_pids = {
        int(r.get("PID") or 0)
        for r in psscan_rows if r.get("PID")
    }

    # Hidden processes: in psscan but NOT in pslist → DKOM rootkit indicator
    hidden_pids = psscan_pids - pslist_pids
    for row in psscan_rows:
        pid = int(row.get("PID") or 0)
        if pid in hidden_pids and pid > 4:
            name = row.get("ImageFileName") or row.get("name") or "unknown"
            findings.append({
                "type": "HIDDEN_PROCESS",
                "severity": "CRITICAL",
                "pid": pid,
                "name": name,
                "ppid": row.get("PPID"),
                "created": row.get("CreateTime") or "",
                "reason": "Process visible in psscan but hidden from pslist — DKOM rootkit indicator",
                "mitre": "T1564.001",
            })
            anomalies.append(f"HIDDEN_PROCESS pid={pid} name={name}")

    # ── 2. Fetch netscan ──────────────────────────────────────────────────────
    netscan_rows, ms = await _run_vol(memory_image, "windows.netstat.NetStat")
    if not netscan_rows:
        netscan_rows, ms = await _run_vol(memory_image, "windows.netscan.NetScan")
    total_ms += ms

    # Orphaned connections: connection PID not in pslist
    for row in netscan_rows:
        pid = int(row.get("PID") or row.get("Pid") or 0)
        state = (row.get("State") or "").upper()
        proto = (row.get("Proto") or row.get("proto") or "")
        foreign = row.get("ForeignAddr") or row.get("foreign_addr") or ""
        if pid == 0 or pid == 4:
            continue
        if pid not in pslist_pids and state in ("ESTABLISHED", "CLOSE_WAIT", "SYN_SENT"):
            findings.append({
                "type": "ORPHANED_CONNECTION",
                "severity": "HIGH",
                "pid": pid,
                "proto": proto,
                "state": state,
                "foreign_addr": foreign,
                "reason": "Network connection from PID not present in process list — process may have terminated after establishing connection or be hidden",
                "mitre": "T1071",
            })
            anomalies.append(f"ORPHANED_CONNECTION pid={pid} {state} → {foreign}")

    # ── 3. Truncated process names ────────────────────────────────────────────
    for row in pslist_rows:
        name = row.get("ImageFileName") or row.get("name") or ""
        pid  = int(row.get("PID") or 0)
        if name.endswith(".e") or (len(name) == 14 and "." not in name[-4:]):
            findings.append({
                "type": "TRUNCATED_PROCESS_NAME",
                "severity": "HIGH",
                "pid": pid,
                "name": name,
                "ppid": row.get("PPID"),
                "reason": "Process name truncated at 14 chars — binary likely has longer name to evade name-based detection",
                "mitre": "T1036",
            })
            anomalies.append(f"TRUNCATED_NAME pid={pid} name={name}")

    # ── 4. Wow64 anomalies — 32-bit processes from system parent ─────────────
    system_ppids = {4, 660, 532}  # System, services.exe, wininit.exe
    for row in pslist_rows:
        wow64 = str(row.get("Wow64") or "").lower() in ("true", "1")
        ppid  = int(row.get("PPID") or 0)
        pid   = int(row.get("PID") or 0)
        name  = row.get("ImageFileName") or ""
        if wow64 and ppid in system_ppids:
            findings.append({
                "type": "WOW64_ANOMALY",
                "severity": "MEDIUM",
                "pid": pid,
                "name": name,
                "ppid": ppid,
                "reason": "32-bit (Wow64) process spawned directly from system process — unusual, warrants inspection",
                "mitre": "T1055",
            })
            anomalies.append(f"WOW64_ANOMALY pid={pid} name={name} ppid={ppid}")

    # ── Summary ───────────────────────────────────────────────────────────────
    critical = sum(1 for f in findings if f.get("severity") == "CRITICAL")
    high     = sum(1 for f in findings if f.get("severity") == "HIGH")

    summary = (
        f"{len(findings)} correlation anomalies: "
        f"{critical} CRITICAL, {high} HIGH | "
        f"hidden={len(hidden_pids)} orphaned_conns={sum(1 for f in findings if f['type']=='ORPHANED_CONNECTION')} "
        f"truncated={sum(1 for f in findings if f['type']=='TRUNCATED_PROCESS_NAME')}"
    )

    return ForensicResult(
        tool="correlate_findings",
        outcome=ToolOutcome.OK,
        summary=summary,
        findings=findings[:100],
        raw_excerpt="\n".join(anomalies[:20]),
        evidence_refs=[memory_image],
        duration_ms=total_ms,
    )
