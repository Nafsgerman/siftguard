from __future__ import annotations

from siftguard.mcp_server.safe_exec import SafeExecError, safe_exec
from siftguard.models.forensic import ForensicResult, ToolOutcome


async def create_supertimeline(
    *,
    evidence_path: str,
    output_plaso: str = "/tmp/siftguard_timeline.plaso",
    storage_file: str = "/tmp/siftguard_timeline.csv",
    filter_date_start: str | None = None,
    filter_date_end: str | None = None,
) -> ForensicResult:
    """Run log2timeline to create a plaso supertimeline from evidence."""
    args = [
        "--storage-file",
        output_plaso,
        "--parsers",
        "win7,winevtx,mft,prefetch,registry,lnk,pe",
        "--hashers",
        "md5,sha256",
        evidence_path,
    ]
    try:
        result = await safe_exec("log2timeline.py", args, timeout_s=3600)
    except SafeExecError as e:
        return ForensicResult(
            tool="create_supertimeline",
            outcome=ToolOutcome.FAIL,
            summary=str(e),
            duration_ms=0,
            error=str(e),
        )

    if result.returncode != 0:
        return ForensicResult(
            tool="create_supertimeline",
            outcome=ToolOutcome.FAIL,
            summary="log2timeline failed",
            raw_excerpt=result.stderr[:1500],
            duration_ms=result.duration_ms,
            error=result.stderr[:500],
        )

    return ForensicResult(
        tool="create_supertimeline",
        outcome=ToolOutcome.OK,
        summary=f"supertimeline created at {output_plaso}",
        findings=[{"plaso_file": output_plaso}],
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[evidence_path],
        duration_ms=result.duration_ms,
    )


async def sort_timeline(
    *,
    plaso_file: str,
    output_csv: str = "/tmp/siftguard_sorted.csv",
    filter_date_start: str | None = None,
    filter_date_end: str | None = None,
) -> ForensicResult:
    """Run psort on a plaso file to produce a sorted, filterable CSV timeline."""
    args = ["-o", "l2tcsv", "-w", output_csv]
    if filter_date_start:
        args += ["--slice", filter_date_start]
    args.append(plaso_file)

    try:
        result = await safe_exec("psort.py", args, timeout_s=1800)
    except SafeExecError as e:
        return ForensicResult(
            tool="sort_timeline",
            outcome=ToolOutcome.FAIL,
            summary=str(e),
            duration_ms=0,
            error=str(e),
        )

    if result.returncode != 0:
        return ForensicResult(
            tool="sort_timeline",
            outcome=ToolOutcome.FAIL,
            summary="psort failed",
            raw_excerpt=result.stderr[:1500],
            duration_ms=result.duration_ms,
            error=result.stderr[:500],
        )

    return ForensicResult(
        tool="sort_timeline",
        outcome=ToolOutcome.OK,
        summary=f"sorted timeline written to {output_csv}",
        findings=[{"csv_file": output_csv}],
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[plaso_file],
        duration_ms=result.duration_ms,
    )
