from __future__ import annotations
import shutil
from siftguard.models.forensic import ForensicResult, ToolOutcome
from siftguard.mcp_server.safe_exec import safe_exec, SafeExecError
from siftguard.parsers.mft_parser import parse_analyze_mft_csv

_ANALYZERMFT_CANDIDATES = [
    "/usr/local/bin/analyzeMFT.py",
    "/usr/bin/analyzeMFT.py",
    shutil.which("analyzeMFT.py") or "",
    shutil.which("analyzeMFT") or "",
]

def _get_analyzeMFT_cmd() -> list[str]:
    for c in _ANALYZERMFT_CANDIDATES:
        if c and __import__("pathlib").Path(c).exists():
            return ["python3", c]
    return ["python3", "-m", "analyzeMFT"]


async def analyze_mft(*, mft_path: str,
                      output_csv: str = "/tmp/siftguard_mft.csv",
                      timestomp_only: bool = False) -> ForensicResult:
    try:
        cmd_prefix = _get_analyzeMFT_cmd()
        result = await safe_exec(
            cmd_prefix[0],
            cmd_prefix[1:] + ["-f", mft_path, "-o", output_csv,
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
