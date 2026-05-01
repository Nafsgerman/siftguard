from __future__ import annotations
from siftguard.models.forensic import ForensicResult, ToolOutcome
from siftguard.mcp_server.safe_exec import safe_exec, SafeExecError
from siftguard.parsers.mft_parser import parse_analyze_mft_csv


async def analyze_mft(*, mft_path: str,
                      output_csv: str = "/tmp/siftguard_mft.csv",
                      timestomp_only: bool = False) -> ForensicResult:
    try:
        result = await safe_exec(
            "analyzeMFT.py",
            ["-f", mft_path, "-o", output_csv,
             "--bodyfile", "/tmp/siftguard_bodyfile.txt"],
            timeout_s=900,
        )
    except SafeExecError as e:
        return ForensicResult(tool="analyze_mft", outcome=ToolOutcome.FAIL,
                              summary=f"safe-exec rejected: {e}",
                              duration_ms=0, error=str(e))

    if result.returncode != 0:
        return ForensicResult(tool="analyze_mft", outcome=ToolOutcome.FAIL,
                              summary="analyzeMFT.py exited non-zero",
                              duration_ms=result.duration_ms,
                              raw_excerpt=result.stderr[:1500],
                              error=result.stderr[:500])

    entries = parse_analyze_mft_csv(output_csv)
    if timestomp_only:
        entries = [e for e in entries if e.timestomp_suspected]

    timestomp_count = sum(1 for e in entries if e.timestomp_suspected)
    summary = f"parsed {len(entries)} MFT entries, {timestomp_count} timestomp-suspected"

    return ForensicResult(
        tool="analyze_mft", outcome=ToolOutcome.OK, summary=summary,
        findings=[e.model_dump(mode="json") for e in entries[:200]],
        raw_excerpt=result.stdout[:1500],
        evidence_refs=[mft_path],
        duration_ms=result.duration_ms,
    )
