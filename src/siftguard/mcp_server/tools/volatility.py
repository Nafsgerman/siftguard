from __future__ import annotations

import contextlib
import json
from pathlib import Path

from siftguard.mcp_server.safe_exec import SafeExecError, safe_exec
from siftguard.models.forensic import ForensicResult, ToolOutcome
from siftguard.parsers.volatility_parser import parse_malfind, parse_netscan, parse_pslist

VOL3 = "/opt/volatility3/bin/vol"


def _cache_dir(memory_image: str) -> Path:
    """Case-scoped cache: derives from the image path, not hardcoded."""
    image_path = Path(memory_image)
    # /cases/TEST-001/memory.mem  → /cases/TEST-001/siftguard_cache
    # /tmp/anything.mem           → /tmp/siftguard_cache_anything
    parent = image_path.parent
    cache = Path(os.environ.get("SIFTGUARD_CACHE_DIR", str(parent / "siftguard_cache")))
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def _cache_path(tool_name: str, memory_image: str) -> Path:
    return _cache_dir(memory_image) / f"{tool_name}.jsonl"


def _load_cache(tool_name: str, path: Path) -> ForensicResult | None:
    try:
        findings = []
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            with contextlib.suppress(json.JSONDecodeError):
                findings.append(json.loads(line))
        return ForensicResult(
            tool=tool_name,
            outcome=ToolOutcome.OK,
            summary=f"(cached) {len(findings)} records",
            findings=findings,
            duration_ms=0,
        )
    except Exception:
        return None


def _save_cache(path: Path, result: ForensicResult) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(f) for f in result.findings))
    except Exception:
        pass


async def vol_pslist(*, memory_image: str) -> ForensicResult:
    """List all processes from a memory image. Flags orphans and suspicious names."""
    cache = _cache_path("vol_pslist", memory_image)
    if cached := _load_cache("vol_pslist", cache):
        return cached

    args = ["-f", memory_image, "-r", "jsonl", "windows.psscan"]
    try:
        result = await safe_exec(VOL3, args, timeout_s=900)
    except SafeExecError as e:
        return ForensicResult(
            tool="vol_pslist", outcome=ToolOutcome.FAIL, summary=str(e), duration_ms=0, error=str(e)
        )

    if result.returncode != 0:
        return ForensicResult(
            tool="vol_pslist",
            outcome=ToolOutcome.FAIL,
            summary="volatility psscan failed",
            raw_excerpt=result.stderr[:1500],
            duration_ms=result.duration_ms,
            error=result.stderr[:500],
        )

    processes = parse_pslist(result.stdout)
    suspicious = [p for p in processes if p.suspicious_indicators]
    fr = ForensicResult(
        tool="vol_pslist",
        outcome=ToolOutcome.OK,
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
    cache = _cache_path("vol_netscan", memory_image)
    if cached := _load_cache("vol_netscan", cache):
        return cached

    args = ["-f", memory_image, "-r", "jsonl", "windows.netscan"]
    try:
        result = await safe_exec(VOL3, args, timeout_s=900)
    except SafeExecError as e:
        return ForensicResult(
            tool="vol_netscan",
            outcome=ToolOutcome.FAIL,
            summary=str(e),
            duration_ms=0,
            error=str(e),
        )

    if result.returncode != 0:
        return ForensicResult(
            tool="vol_netscan",
            outcome=ToolOutcome.FAIL,
            summary="volatility netscan failed",
            raw_excerpt=result.stderr[:1500],
            duration_ms=result.duration_ms,
            error=result.stderr[:500],
        )

    connections = parse_netscan(result.stdout)
    fr = ForensicResult(
        tool="vol_netscan",
        outcome=ToolOutcome.OK,
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
    cache = _cache_path("vol_malfind", memory_image)
    if cached := _load_cache("vol_malfind", cache):
        return cached

    args = ["-f", memory_image, "-r", "jsonl", "windows.malfind"]
    try:
        result = await safe_exec(VOL3, args, timeout_s=1200)
    except SafeExecError as e:
        return ForensicResult(
            tool="vol_malfind",
            outcome=ToolOutcome.FAIL,
            summary=str(e),
            duration_ms=0,
            error=str(e),
        )

    if result.returncode != 0:
        return ForensicResult(
            tool="vol_malfind",
            outcome=ToolOutcome.FAIL,
            summary="volatility malfind failed",
            raw_excerpt=result.stderr[:1500],
            duration_ms=result.duration_ms,
            error=result.stderr[:500],
        )

    hits = parse_malfind(result.stdout)
    fr = ForensicResult(
        tool="vol_malfind",
        outcome=ToolOutcome.OK,
        summary=f"{len(hits)} suspicious memory regions found",
        findings=hits,
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[memory_image],
        duration_ms=result.duration_ms,
    )
    _save_cache(cache, fr)
    return fr
