from __future__ import annotations

import json
import os
from pathlib import Path

from siftguard.mcp_server.safe_exec import SafeExecError, safe_exec
from siftguard.models.forensic import ForensicResult, ToolOutcome

VOL3 = "/opt/volatility3/bin/vol"
CACHE_DIR = Path(os.environ.get("SIFTGUARD_CACHE_DIR", "/cases/TEST-001/siftguard_cache"))


def _cache_path(plugin: str) -> Path:
    return CACHE_DIR / f"{plugin}.json"


def _read_cache(plugin: str) -> tuple[str, int] | None:
    """Return (stdout, duration_ms) if cache exists. Strips Volatility header. Caps at 50MB."""
    p = _cache_path(plugin)
    if not p.exists() or p.stat().st_size < 50:
        return None
    MAX_BYTES = 50 * 1024 * 1024
    with p.open("r", errors="replace") as f:
        text = f.read(MAX_BYTES)
    if text.startswith("Volatility"):
        text = text[text.index("\n") + 1 :].lstrip()
    if len(text) == MAX_BYTES:
        last = text.rfind("\n  },")
        if last > 0:
            text = text[: last + 4] + "\n]"
    return text, 0


async def _run_or_cache(
    plugin: str, memory_image: str, timeout_s: int = 300
) -> tuple[str, int, str | None]:
    """Returns (stdout, duration_ms, error). Reads cache if present, else runs Volatility and caches."""
    cached = _read_cache(plugin)
    if cached:
        return cached[0], cached[1], None
    try:
        result = await safe_exec(
            VOL3,
            ["-q", "-f", memory_image, "-r", "json", plugin],
            timeout_s=timeout_s,
        )
    except SafeExecError as e:
        return "", 0, str(e)
    if result.returncode != 0:
        return result.stdout, result.duration_ms, result.stderr[:500] or "non-zero exit"
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(plugin).write_text(result.stdout)
    except Exception:
        pass
    return result.stdout, result.duration_ms, None


async def analyze_mft(
    *,
    memory_image: str,
    mft_path: str = "",
    timestomp_only: bool = False,
) -> ForensicResult:
    """Scan MFT entries directly from memory via Volatility3 MFTScan. READ-ONLY. Cached."""
    stdout, duration_ms, err = await _run_or_cache("windows.mftscan.MFTScan", memory_image)
    if err:
        return ForensicResult(
            tool="analyze_mft",
            outcome=ToolOutcome.FAIL,
            summary=err,
            duration_ms=duration_ms,
            error=err,
        )

    entries = []
    try:
        raw = json.loads(stdout)
        for r in raw:
            filename = r.get("Filename") or r.get("filename") or ""
            created = r.get("Created") or r.get("created") or ""
            modified = r.get("Updated") or r.get("modified") or ""
            record_num = r.get("Record Number") or r.get("record_number") or 0
            in_use = str(r.get("InUse") or r.get("in_use") or "").lower() in ("true", "1", "yes")
            file_type = "Directory" if str(r.get("Type") or "").lower() == "directory" else "File"
            si_c = r.get("SI Created") or r.get("si_created") or ""
            fn_c = r.get("FN Created") or r.get("fn_created") or ""
            timestomp = bool(si_c and fn_c and si_c < fn_c)
            entries.append(
                {
                    "record_number": record_num,
                    "filename": filename,
                    "in_use": in_use,
                    "file_type": file_type,
                    "created": created,
                    "modified": modified,
                    "timestomp_suspected": timestomp,
                    "raw": r,
                }
            )
    except Exception as e:
        return ForensicResult(
            tool="analyze_mft",
            outcome=ToolOutcome.FAIL,
            summary=f"JSON parse failed: {e}",
            raw_excerpt=stdout[:1500],
            duration_ms=duration_ms,
            error=str(e),
        )

    if timestomp_only:
        entries = [e for e in entries if e["timestomp_suspected"]]
    timestomp_count = sum(1 for e in entries if e["timestomp_suspected"])
    suspicious = _flag_suspicious(entries)

    return ForensicResult(
        tool="analyze_mft",
        outcome=ToolOutcome.OK,
        summary=f"{len(entries)} MFT entries, {timestomp_count} timestomp-suspected, {len(suspicious)} suspicious",
        findings=entries[:200],
        raw_excerpt=stdout[:1500],
        evidence_refs=[memory_image],
        duration_ms=duration_ms,
    )


async def scan_mft_ads(*, memory_image: str) -> ForensicResult:
    """Scan for Alternate Data Streams in MFT. READ-ONLY. Cached."""
    stdout, duration_ms, err = await _run_or_cache("windows.mftscan.ADS", memory_image)
    if err:
        return ForensicResult(
            tool="scan_mft_ads",
            outcome=ToolOutcome.FAIL,
            summary=err,
            duration_ms=duration_ms,
            error=err,
        )
    try:
        findings = json.loads(stdout)
    except Exception:
        findings = []
    return ForensicResult(
        tool="scan_mft_ads",
        outcome=ToolOutcome.OK,
        summary=f"{len(findings)} alternate data streams found",
        findings=findings[:100],
        raw_excerpt=stdout[:1500],
        evidence_refs=[memory_image],
        duration_ms=duration_ms,
    )


def _flag_suspicious(entries: list[dict]) -> list[dict]:
    suspicious = []
    sus_paths = ["\\temp\\", "\\appdata\\", "\\windows\\temp", "\\recycle"]
    sus_exts = [".exe", ".dll", ".bat", ".ps1", ".vbs", ".cmd"]
    for e in entries:
        fn = (e.get("filename") or "").lower()
        if any(p in fn for p in sus_paths) and any(fn.endswith(x) for x in sus_exts):
            e["suspicious_reason"] = "executable in temp/appdata path"
            suspicious.append(e)
        elif e.get("timestomp_suspected"):
            e["suspicious_reason"] = "timestomp detected"
            suspicious.append(e)
    return suspicious
