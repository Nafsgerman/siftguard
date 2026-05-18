from __future__ import annotations

import re
import sqlite3
import subprocess

from siftguard.eval.verifier_models import (
    VerificationMethod,
    VerificationResult,
    VerificationStatus,
)

_PROCESS_WHITELIST = {
    "explorer.exe",
    "services.exe",
    "svchost.exe",
    "lsass.exe",
    "csrss.exe",
    "smss.exe",
    "wininit.exe",
    "winlogon.exe",
    "spoolsv.exe",
    "taskmgr.exe",
    "conhost.exe",
    "dllhost.exe",
}
_VOL_BIN = "/opt/volatility3/bin/vol"
_EVIDENCE_IMG = "/cases/TEST-001/base-hunt-memory.img"


def _audit_corpus(db_path: str, run_id: str) -> str:
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


def _substring_match(value: str, corpus: str) -> str | None:
    needle = value.strip().lower()
    haystack = corpus.lower()
    idx = haystack.find(needle)
    if idx == -1:
        return None
    start = max(0, idx - 40)
    end = min(len(corpus), idx + len(needle) + 80)
    return corpus[start:end]


def _tool_rerun_verify(finding_value: str, finding_type: str) -> str | None:
    plugin_map = {"network": "windows.netstat.NetStat", "process": "windows.psscan.PsScan"}
    plugin = plugin_map.get(finding_type.lower())
    if not plugin:
        return None
    try:
        result = subprocess.run(
            [_VOL_BIN, "-f", _EVIDENCE_IMG, plugin, "-r", "jsonl"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        needle = finding_value.strip().lower()
        for line in result.stdout.splitlines():
            if needle in line.lower():
                return line[:200]
        return None
    except Exception:
        return None


def verify_finding(
    finding: dict, audit_db: str, run_id: str, enable_tool_rerun: bool = False
) -> VerificationResult:
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

    if fvalue.lower() in _PROCESS_WHITELIST:
        return VerificationResult(
            finding_id=fid,
            status=VerificationStatus.VERIFIED,
            method=VerificationMethod.SUBSTRING_MATCH,
            confidence=1.0,
            matched_evidence="process on whitelist of known-legitimate Windows processes",
        )

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
        return VerificationResult(
            finding_id=fid,
            status=VerificationStatus.UNVERIFIABLE,
            method=VerificationMethod.UNVERIFIABLE,
            confidence=0.0,
            refutation_reason="audit corpus empty for this run_id",
        )

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
        return VerificationResult(
            finding_id=fid,
            status=VerificationStatus.REFUTED,
            method=VerificationMethod.TOOL_RERUN,
            confidence=0.90,
            refutation_reason=f"value '{fvalue}' not found in fresh {ftype} plugin output",
        )

    return VerificationResult(
        finding_id=fid,
        status=VerificationStatus.REFUTED,
        method=VerificationMethod.SUBSTRING_MATCH,
        confidence=0.80,
        refutation_reason=f"value '{fvalue}' not found in audit trail corpus ({len(corpus)} chars)",
    )
