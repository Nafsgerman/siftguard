from __future__ import annotations

from pathlib import Path

from siftguard.mcp_server.safe_exec import SafeExecError, safe_exec
from siftguard.models.forensic import ForensicResult, ToolOutcome
from siftguard.parsers.filesystem_parser import parse_fls_output

FLS = "/usr/bin/fls"
ICAT = "/usr/bin/icat"


async def list_files(
    *,
    image_path: str,
    inode: str = "",
    offset: str = "",
    recursive: bool = True,
) -> ForensicResult:
    """List files in a disk image partition using fls (TSK). READ-ONLY."""
    args = ["-r"] if recursive else []
    if offset:
        args += ["-o", offset]
    args.append(image_path)
    if inode:
        args.append(inode)

    try:
        result = await safe_exec(FLS, args, timeout_s=300)
    except SafeExecError as e:
        return ForensicResult(
            tool="list_files", outcome=ToolOutcome.FAIL, summary=str(e), duration_ms=0, error=str(e)
        )

    if result.returncode != 0:
        return ForensicResult(
            tool="list_files",
            outcome=ToolOutcome.FAIL,
            summary="fls failed",
            raw_excerpt=result.stderr[:1500],
            duration_ms=result.duration_ms,
            error=result.stderr[:500],
        )

    entries = parse_fls_output(result.stdout)
    deleted = [e for e in entries if e.get("deleted")]
    suspicious = _flag_suspicious_files(entries)

    return ForensicResult(
        tool="list_files",
        outcome=ToolOutcome.OK,
        summary=f"{len(entries)} entries, {len(deleted)} deleted, {len(suspicious)} suspicious",
        findings=entries[:500],
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[image_path],
        duration_ms=result.duration_ms,
    )


async def extract_file(
    *,
    image_path: str,
    inode: str,
    output_path: str,
    offset: str = "",
) -> ForensicResult:
    """Extract a file from a disk image by inode using icat. READ-ONLY."""
    args = []
    if offset:
        args += ["-o", offset]
    args += [image_path, inode]

    try:
        result = await safe_exec(ICAT, args, timeout_s=120)
    except SafeExecError as e:
        return ForensicResult(
            tool="extract_file",
            outcome=ToolOutcome.FAIL,
            summary=str(e),
            duration_ms=0,
            error=str(e),
        )

    if result.returncode != 0:
        return ForensicResult(
            tool="extract_file",
            outcome=ToolOutcome.FAIL,
            summary=f"icat failed for inode {inode}",
            raw_excerpt=result.stderr[:1500],
            duration_ms=result.duration_ms,
            error=result.stderr[:500],
        )

    # Write extracted bytes to output_path
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(result.stdout.encode() if isinstance(result.stdout, str) else result.stdout)

    return ForensicResult(
        tool="extract_file",
        outcome=ToolOutcome.OK,
        summary=f"extracted inode {inode} → {output_path} ({out.stat().st_size} bytes)",
        findings=[{"inode": inode, "output_path": output_path, "bytes": out.stat().st_size}],
        raw_excerpt=result.stdout[:500] if isinstance(result.stdout, str) else "",
        evidence_refs=[image_path],
        duration_ms=result.duration_ms,
    )


def _flag_suspicious_files(entries: list[dict]) -> list[dict]:
    sus_exts = [".exe", ".dll", ".bat", ".ps1", ".vbs", ".cmd", ".scr"]
    sus_dirs = ["temp", "tmp", "appdata", "recycle", "windows\\system32\\config"]
    suspicious = []
    for e in entries:
        name = (e.get("name") or "").lower()
        if e.get("deleted") and any(name.endswith(x) for x in sus_exts):
            e["suspicious_reason"] = "deleted executable"
            suspicious.append(e)
        elif any(d in name for d in sus_dirs) and any(name.endswith(x) for x in sus_exts):
            e["suspicious_reason"] = "executable in suspicious path"
            suspicious.append(e)
    return suspicious
