from __future__ import annotations

import sqlite3
import subprocess
import json
import re
from typing import Optional

from siftguard.eval.verifier_models import (
    VerificationMethod,
    VerificationResult,
    VerificationStatus,
)


# Processes that are always legitimate — never flag as IOC
_PROCESS_WHITELIST = {
    "explorer.exe", "services.exe", "svchost.exe", "lsass.exe",
    "csrss.exe", "smss.exe", "wininit.exe", "winlogon.exe",
    "spoolsv.exe", "taskmgr.exe", "conhost.exe", "dllhost.exe",
}

_VOL_BIN = "/opt/volatility3/bin/vol"
_EVIDENCE_IMG = "/cases/TEST-001/base-hunt-memory.img"


def _audit_corpus(db_path: str, run_id: str) -> str:
    """Pull all tool output text for this run from the audit DB."""
    try:
        con = sqlite3.connect(db_path)
        cur = con.execute(
            "SELECT tool_output FROM auditentry WHERE run_id = ? AND tool_output IS NOT NULL",
            (run_id,),
        )
        rows = cur.fetchall()
        con.close()
        return "\n".join(r[0] for r in rows if r[0])
    except Exception:
        return ""


def _substring_match(value: str, corpus: str) -> Optional[str]:
    """Return the first 120-char context window around the match, or None."""
    needle = value.strip().lower()
    haystack = corpus.lower()
    idx = haystack.find(needle)
    if idx == -1:
        return None
    start = max(0, idx - 40)
    end = min(len(corpus), idx + len(needle) + 80)
    return corpus[start:end]


def _tool_rerun_verify(finding_value: str, finding_type: str) -> Optional[str]:
    """
    Slow path: re-run the most relevant Volatility plugin and grep output.
    Only called for verdict-level findings (finding_type == 'network' or 'process').
    Returns raw snippet on hit, None on miss.
    """
    plugin_map = {
        "network": "windows.netstat.NetStat",
        "process": "windows.psscan.PsScan",
    }
    plugin = plugin_map.get(finding_type.lower())
    if not plugin:
        return None

    try:
        result = subprocess.run(
            [_VOL_BIN, "-f", _EVIDENCE_IMG, plugin, "-r", "jsonl"],
            capture_output=True, text=True, timeout=120
        )
        output = result.stdout
        needle = finding_value.strip().lower()
        for line in output.splitlines():
            if needle in line.lower():
                return line[:200]
        return None
    except Exception:
        return None


def verify_finding(
    finding: dict,
    audit_db: str,
    run_id: str,
    enable_tool_rerun: bool = False,
) -> VerificationResult:
    """
    Hybrid A+B hallucination verifier.

    Path A (default): substring match against audit trail corpus — fast, free, zero API calls.
    Path B (slow): Volatility tool re-run — only when enable_tool_rerun=True AND finding is
                   verdict-level (type in ['network', 'process']).

    Args:
        finding: dict with keys: id, value, type, description
        audit_db: path to SQLite audit DB
        run_id: current run ID to scope corpus
        enable_tool_rerun: gate for slow path

    Returns:
        VerificationResult
    """
    fid = finding.get("id", "unknown")
    fvalue = finding.get("value", "").strip()
    ftype = finding.get("type", "").strip().lower()
    fdesc = finding.get("description", "").strip()

    if not fvalue:
        return VerificationResult(
            finding_id=fid,
            status=VerificationStatus.UNVERIFIABLE,
            method=VerificationMethod.UNVERIFIABLE,
            confidence=0.0,
            refutation_reason="finding value is empty",
        )

    # Whitelist check — legitimate processes are always verified
    if fvalue.lower() in _PROCESS_WHITELIST:
        return VerificationResult(
            finding_id=fid,
            status=VerificationStatus.VERIFIED,
            method=VerificationMethod.SUBSTRING_MATCH,
            confidence=1.0,
            matched_evidence="process on whitelist of known-legitimate Windows processes",
        )

    # Path A: substring match against audit corpus
    corpus = _audit_corpus(audit_db, run_id)

    if corpus:
        snippet = _substring_match(fvalue, corpus)
        if snippet:
            return VerificationResult(
                finding_id=fid,
                status=VerificationStatus.VERIFIED,
                method=VerificationMethod.SUBSTRING_MATCH,
                confidence=0.95,
                matched_evidence=snippet,
            )

        # Also try matching description keywords (first 6 words)
        desc_tokens = re.findall(r"\b\w{5,}\b", fdesc)[:6]
        for token in desc_tokens:
            snip = _substring_match(token, corpus)
            if snip:
                return VerificationResult(
                    finding_id=fid,
                    status=VerificationStatus.VERIFIED,
                    method=VerificationMethod.SUBSTRING_MATCH,
                    confidence=0.75,
                    matched_evidence=snip,
                )
    else:
        # Empty corpus → unverifiable, not refuted
        return VerificationResult(
            finding_id=fid,
            status=VerificationStatus.UNVERIFIABLE,
            method=VerificationMethod.UNVERIFIABLE,
            confidence=0.0,
            refutation_reason="audit corpus empty for this run_id",
        )

    # Path B: tool re-run (slow path, verdict-level only)
    if enable_tool_rerun and ftype in ("network", "process"):
        tool_snip = _tool_rerun_verify(fvalue, ftype)
        if tool_snip:
            return VerificationResult(
                finding_id=fid,
                status=VerificationStatus.VERIFIED,
                method=VerificationMethod.TOOL_RERUN,
                confidence=0.99,
                tool_output_snippet=tool_snip,
            )
        else:
            return VerificationResult(
                finding_id=fid,
                status=VerificationStatus.REFUTED,
                method=VerificationMethod.TOOL_RERUN,
                confidence=0.90,
                refutation_reason=f"value '{fvalue}' not found in fresh {ftype} plugin output",
            )

    # No match found in corpus, tool rerun not enabled → refuted
    return VerificationResult(
        finding_id=fid,
        status=VerificationStatus.REFUTED,
        method=VerificationMethod.SUBSTRING_MATCH,
        confidence=0.80,
        refutation_reason=f"value '{fvalue}' not found in audit trail corpus ({len(corpus)} chars)",
    )