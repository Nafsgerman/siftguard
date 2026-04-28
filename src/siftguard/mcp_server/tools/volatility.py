from __future__ import annotations
import asyncio
from siftguard.models.forensic import ForensicResult, ToolOutcome, VolatilityProcess
from siftguard.mcp_server.safe_exec import safe_exec, SafeExecError
from siftguard.parsers.volatility_parser import parse_pslist, parse_netscan, parse_malfind

VOL3 = "/opt/volatility3/bin/vol"


async def vol_pslist(*, memory_image: str) -> ForensicResult:
    """List all processes from a memory image. Flags orphans and suspicious names."""
    try:
        result = await safe_exec(
            VOL3, ["-f", memory_image, "-r", "jsonl", "windows.psscan"],
            timeout_s=300,
        )
    except SafeExecError as e:
        return ForensicResult(tool="vol_pslist", outcome=ToolOutcome.FAIL,
                              summary=str(e), duration_ms=0, error=str(e))

    if result.returncode != 0:
        return ForensicResult(tool="vol_pslist", outcome=ToolOutcome.FAIL,
                              summary="volatility psscan failed",
                              raw_excerpt=result.stderr[:1500],
                              duration_ms=result.duration_ms,
                              error=result.stderr[:500])

    processes = parse_pslist(result.stdout)
    suspicious = [p for p in processes if p.suspicious_indicators]

    return ForensicResult(
        tool="vol_pslist", outcome=ToolOutcome.OK,
        summary=f"{len(processes)} processes, {len(suspicious)} suspicious",
        findings=[p.model_dump(mode="json") for p in processes],
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[memory_image],
        duration_ms=result.duration_ms,
    )


async def vol_netscan(*, memory_image: str) -> ForensicResult:
    """Scan memory image for network connections and listening ports."""
    try:
        result = await safe_exec(
            VOL3, ["-f", memory_image, "-r", "jsonl", "windows.netscan"],
            timeout_s=300,
        )
    except SafeExecError as e:
        return ForensicResult(tool="vol_netscan", outcome=ToolOutcome.FAIL,
                              summary=str(e), duration_ms=0, error=str(e))

    if result.returncode != 0:
        return ForensicResult(tool="vol_netscan", outcome=ToolOutcome.FAIL,
                              summary="volatility netscan failed",
                              raw_excerpt=result.stderr[:1500],
                              duration_ms=result.duration_ms,
                              error=result.stderr[:500])

    connections = parse_netscan(result.stdout)
    return ForensicResult(
        tool="vol_netscan", outcome=ToolOutcome.OK,
        summary=f"{len(connections)} network connections found",
        findings=connections,
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[memory_image],
        duration_ms=result.duration_ms,
    )


async def vol_malfind(*, memory_image: str) -> ForensicResult:
    """Find injected code and suspicious memory regions."""
    try:
        result = await safe_exec(
            VOL3, ["-f", memory_image, "-r", "jsonl", "windows.malfind"],
            timeout_s=600,
        )
    except SafeExecError as e:
        return ForensicResult(tool="vol_malfind", outcome=ToolOutcome.FAIL,
                              summary=str(e), duration_ms=0, error=str(e))

    if result.returncode != 0:
        return ForensicResult(tool="vol_malfind", outcome=ToolOutcome.FAIL,
                              summary="volatility malfind failed",
                              raw_excerpt=result.stderr[:1500],
                              duration_ms=result.duration_ms,
                              error=result.stderr[:500])

    hits = parse_malfind(result.stdout)
    return ForensicResult(
        tool="vol_malfind", outcome=ToolOutcome.OK,
        summary=f"{len(hits)} suspicious memory regions found",
        findings=hits,
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[memory_image],
        duration_ms=result.duration_ms,
    )