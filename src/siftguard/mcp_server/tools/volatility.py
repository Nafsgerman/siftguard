from __future__ import annotations
import hashlib
import json
from pathlib import Path
from siftguard.models.forensic import ForensicResult, ToolOutcome, VolatilityProcess
from siftguard.mcp_server.safe_exec import safe_exec, SafeExecError
from siftguard.parsers.volatility_parser import parse_pslist, parse_netscan, parse_malfind

VOL3 = "/opt/volatility3/bin/vol"
_CACHE_DIR = Path("/tmp/siftguard_cache")


def _cache_path(tool_name: str, args: list[str]) -> Path:
    key = hashlib.sha256(" ".join(args).encode()).hexdigest()[:16]
    return _CACHE_DIR / f"{tool_name}_{key}.json"


def _load_cache(path: Path) -> ForensicResult | None:
    try:
        return ForensicResult.model_validate_json(path.read_text())
    except Exception:
        return None


def _save_cache(path: Path, result: ForensicResult) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(result.model_dump_json())
    except Exception:
        pass


async def vol_pslist(*, memory_image: str) -> ForensicResult:
    """List all processes from a memory image. Flags orphans and suspicious names."""
    args = ["-f", memory_image, "-r", "jsonl", "windows.psscan"]
    cache = _cache_path("vol_pslist", args)
    if cached := _load_cache(cache):
        return cached

    try:
        result = await safe_exec(VOL3, args, timeout_s=900)
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
    fr = ForensicResult(
        tool="vol_pslist", outcome=ToolOutcome.OK,
        summary=f"{len(processes)} processes, {len(suspicious)} suspicious",
        findings=[p.model_dump(mode="json") for p in processes],
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[memory_image],
        duration_ms=result.duration_ms,
    )
    _save_cache(cache, fr)
    return fr


async def vol_netscan(*, memory_image: str) -> ForensicResult:
    """Scan memory image for network connections and listening ports."""
    args = ["-f", memory_image, "-r", "jsonl", "windows.netscan"]
    cache = _cache_path("vol_netscan", args)
    if cached := _load_cache(cache):
        return cached

    try:
        result = await safe_exec(VOL3, args, timeout_s=900)
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
    fr = ForensicResult(
        tool="vol_netscan", outcome=ToolOutcome.OK,
        summary=f"{len(connections)} network connections found",
        findings=connections,
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[memory_image],
        duration_ms=result.duration_ms,
    )
    _save_cache(cache, fr)
    return fr


async def vol_malfind(*, memory_image: str) -> ForensicResult:
    """Find injected code and suspicious memory regions."""
    args = ["-f", memory_image, "-r", "jsonl", "windows.malfind"]
    cache = _cache_path("vol_malfind", args)
    if cached := _load_cache(cache):
        return cached

    try:
        result = await safe_exec(VOL3, args, timeout_s=1200)
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
    fr = ForensicResult(
        tool="vol_malfind", outcome=ToolOutcome.OK,
        summary=f"{len(hits)} suspicious memory regions found",
        findings=hits,
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[memory_image],
        duration_ms=result.duration_ms,
    )
    _save_cache(cache, fr)
    return fr
