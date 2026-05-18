"""Panel 8 — Hallucination Verification Rate.

Aggregates VerificationResult across all trace findings.
Reports three rates: verified, refuted (hallucination), unverifiable.
"""

from __future__ import annotations

from typing import Any

from siftguard.eval.verifier_models import VerificationMethod, VerificationStatus


def get_verification_breakdown(traces: list) -> dict[str, Any]:
    total = verified = refuted = unverifiable = 0
    substring_count = tool_rerun_count = unverifiable_method_count = 0

    for trace in traces:
        for finding in trace.findings:
            v = getattr(finding, "verification", None)
            if v is None:
                continue
            total += 1
            if v.status == VerificationStatus.VERIFIED:
                verified += 1
            elif v.status == VerificationStatus.REFUTED:
                refuted += 1
            else:
                unverifiable += 1

            if v.method == VerificationMethod.SUBSTRING_MATCH:
                substring_count += 1
            elif v.method == VerificationMethod.TOOL_RERUN:
                tool_rerun_count += 1
            else:
                unverifiable_method_count += 1

    safe = max(total, 1)
    return {
        "total": total,
        "verified": verified,
        "refuted": refuted,
        "unverifiable": unverifiable,
        "hallucination_rate": refuted / safe,
        "verified_rate": verified / safe,
        "unverifiable_rate": unverifiable / safe,
        "substring_count": substring_count,
        "tool_rerun_count": tool_rerun_count,
    }


def render_panel_8(traces: list) -> dict[str, Any]:
    """Panel 8 — Hallucination Verification Rate."""
    bd = get_verification_breakdown(traces)

    if bd["total"] == 0:
        return {
            "title": "Panel 8: Hallucination Verification",
            "status": "no_data",
            "summary": "No verified findings in traces. Run verifier first.",
            "data": bd,
        }

    lines = [
        "## Panel 8: Hallucination Verification Rate\n",
        f"**Headline: Hallucination Rate = {bd['hallucination_rate']:.1%}**"
        f"  ({bd['refuted']} refuted / {bd['total']} total findings)\n",
        "| Status | Count | Rate |",
        "|--------|-------|------|",
        f"| ✅ Verified     | {bd['verified']}     | {bd['verified_rate']:.1%} |",
        f"| ❌ Refuted      | {bd['refuted']}      | {bd['hallucination_rate']:.1%} |",
        f"| ❓ Unverifiable | {bd['unverifiable']} | {bd['unverifiable_rate']:.1%} |\n",
        "**Method breakdown:**",
        f"- Substring match: {bd['substring_count']}",
        f"- Tool re-run:     {bd['tool_rerun_count']}",
    ]

    return {
        "title": "Panel 8: Hallucination Verification",
        "status": "ok",
        "summary": "\n".join(lines),
        "data": bd,
    }
