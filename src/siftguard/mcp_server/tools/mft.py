from __future__ import annotations
import json
from pathlib import Path
from siftguard.models.forensic import ForensicResult, ToolOutcome, MFTEntry
from siftguard.mcp_server.safe_exec import safe_exec, SafeExecError

VOL3 = "/opt/volatility3/bin/vol"


async def analyze_mft(
    *,
    memory_image: str,
    mft_path: str = "",          # kept for API compat, ignored
    timestomp_only: bool = False,
) -> ForensicResult:
    """Scan MFT entries directly from memory via Volatility3 MFTScan. READ-ONLY."""
    try:
        result = await safe_exec(
            VOL3,
            ["-q", "-f", memory_image, "-r", "json", "windows.mftscan.MFTScan"],
            timeout_s=300,
        )
    except SafeExecError as e:
        return ForensicResult(tool="analyze_mft", outcome=ToolOutcome.FAIL,
                              summary=str(e), duration_ms=0, error=str(e))

    if result.returncode != 0:
        return ForensicResult(tool="analyze_mft", outcome=ToolOutcome.FAIL,
                              summary="MFTScan failed",
                              raw_excerpt=result.stderr[:1500],
                              duration_ms=result.duration_ms,
                              error=result.stderr[:500])

    # Parse JSON output
    entries = []
    try:
        raw = json.loads(result.stdout)
        for r in raw:
            # Volatility MFTScan fields
            filename   = r.get("Filename") or r.get("filename") or ""
            created    = r.get("Created") or r.get("created") or ""
            modified   = r.get("Updated") or r.get("modified") or ""
            record_num = r.get("Record Number") or r.get("record_number") or 0
            in_use     = str(r.get("InUse") or r.get("in_use") or "").lower() in ("true", "1", "yes")
            file_type  = "Directory" if str(r.get("Type") or "").lower() == "directory" else "File"

            # Timestomp: SI < FN (simplified check on available fields)
            si_c = r.get("SI Created") or r.get("si_created") or ""
            fn_c = r.get("FN Created") or r.get("fn_created") or ""
            timestomp = bool(si_c and fn_c and si_c < fn_c)

            entries.append({
                "record_number": record_num,
                "filename": filename,
                "in_use": in_use,
                "file_type": file_type,
                "created": created,
                "modified": modified,
                "timestomp_suspected": timestomp,
                "raw": r,
            })
    except Exception as e:
        return ForensicResult(tool="analyze_mft", outcome=ToolOutcome.FAIL,
                              summary=f"JSON parse failed: {e}",
                              raw_excerpt=result.stdout[:1500],
                              duration_ms=result.duration_ms, error=str(e))

    if timestomp_only:
        entries = [e for e in entries if e["timestomp_suspected"]]

    timestomp_count = sum(1 for e in entries if e["timestomp_suspected"])
    suspicious = _flag_suspicious(entries)

    return ForensicResult(
        tool="analyze_mft", outcome=ToolOutcome.OK,
        summary=f"{len(entries)} MFT entries, {timestomp_count} timestomp-suspected, {len(suspicious)} suspicious",
        findings=entries[:200],
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[memory_image],
        duration_ms=result.duration_ms,
    )


async def scan_mft_ads(*, memory_image: str) -> ForensicResult:
    """Scan for Alternate Data Streams in MFT. READ-ONLY."""
    try:
        result = await safe_exec(
            VOL3,
            ["-q", "-f", memory_image, "-r", "json", "windows.mftscan.ADS"],
            timeout_s=300,
        )
    except SafeExecError as e:
        return ForensicResult(tool="scan_mft_ads", outcome=ToolOutcome.FAIL,
                              summary=str(e), duration_ms=0, error=str(e))

    if result.returncode != 0:
        return ForensicResult(tool="scan_mft_ads", outcome=ToolOutcome.FAIL,
                              summary="ADS scan failed",
                              raw_excerpt=result.stderr[:1500],
                              duration_ms=result.duration_ms, error=result.stderr[:500])

    try:
        findings = json.loads(result.stdout)
    except Exception:
        findings = []

    return ForensicResult(
        tool="scan_mft_ads", outcome=ToolOutcome.OK,
        summary=f"{len(findings)} alternate data streams found",
        findings=findings[:100],
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[memory_image],
        duration_ms=result.duration_ms,
    )


def _flag_suspicious(entries: list[dict]) -> list[dict]:
    """Flag MFT entries with forensic indicators."""
    suspicious = []
    sus_paths = ["\\temp\\", "\\appdata\\", "\\windows\\temp", "\\recycle"]
    sus_exts  = [".exe", ".dll", ".bat", ".ps1", ".vbs", ".cmd"]
    for e in entries:
        fn = (e.get("filename") or "").lower()
        if any(p in fn for p in sus_paths) and any(fn.endswith(x) for x in sus_exts):
            e["suspicious_reason"] = "executable in temp/appdata path"
            suspicious.append(e)
        elif e.get("timestomp_suspected"):
            e["suspicious_reason"] = "timestomp detected"
            suspicious.append(e)
    return suspicious
