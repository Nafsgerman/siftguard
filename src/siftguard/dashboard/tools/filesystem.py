from __future__ import annotations
from siftguard.models.forensic import ForensicResult, ToolOutcome
from siftguard.mcp_server.safe_exec import safe_exec, SafeExecError
from siftguard.parsers.filesystem_parser import parse_fls_output


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
        result = await safe_exec("fls", args, timeout_s=300)
    except SafeExecError as e:
        return ForensicResult(tool="list_files", outcome=ToolOutcome.FAIL,
                              summary=str(e), duration_ms=0, error=str(e))

    if result.returncode != 0:
        return ForensicResult(tool="list_files", outcome=ToolOutcome.FAIL,
                              summary="fls failed",
                              raw_excerpt=result.stderr[:1500],
                              duration_ms=result.duration_ms,
                              error=result.stderr[:500])

    entries = parse_fls_output(result.stdout)
    deleted = [e for e in entries if e.get("deleted")]

    return ForensicResult(
        tool="list_files", outcome=ToolOutcome.OK,
        summary=f"{len(entries)} entries, {len(deleted)} deleted files recovered",
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
        result = await safe_exec("icat", args, timeout_s=120)
    except SafeExecError as e:
        return ForensicResult(tool="extract_file", outcome=ToolOutcome.FAIL,
                              summary=str(e), duration_ms=0, error=str(e))

    return ForensicResult(
        tool="extract_file", outcome=ToolOutcome.OK,
        summary=f"extracted inode {inode} from {image_path}",
        findings=[{"inode": inode, "bytes": len(result.stdout)}],
        raw_excerpt=result.stdout[:500],
        evidence_refs=[image_path],
        duration_ms=result.duration_ms,
    )
