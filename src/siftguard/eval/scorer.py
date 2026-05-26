"""
Scorer: reads tool_call rows from audit DB by run_id.
Extracts IOC findings via IOC_PRODUCING_TOOLS allowlist + per-tool extractors.
Computes f1_applicable (primary) and f1_total (secondary) against versioned ground truth.

Audit DB schema assumed (auditentry table):
  run_id TEXT, agent_id TEXT, case_id TEXT, event_type TEXT,
  tool_name TEXT, tool_input TEXT, tool_output TEXT, created_at TEXT
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IOC_PRODUCING_TOOLS: frozenset[str] = frozenset(
    {
        "vol_pslist",
        "windows_psscan",
        "vol_psscan",
        "vol_netscan",
        "windows_netscan",
        "vol_malfind",
        "windows_malfind",
        "windows_registry_printkey",
        "windows_mftscan",
        "windows_mftscan_ads",
        "windows_filescan",
        "windows_cmdline",
        "windows_dlllist",
        # disk forensics tools (TEST-002, TEST-003)
        "run_regripper",
        "list_files",
        "extract_file",
        "filesystem_walk",
        "mft_parse",
        "registry_hive_parse",
        "timeline_build",
        "prefetch_parse",
        "browser_history_parse",
        "usn_journal_parse",
        "lnk_file_parse",
        "shellbag_parse",
        "recycle_bin_parse",
    }
)

_TOOL_OUTPUT_EVENT_TYPES = ("tool_call_end", "tool_result", "tool_output")
_GT_ROOT = Path("experiments/ground_truth")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class GroundTruthIOC:
    ioc_id: str
    ioc_type: str
    value: str  # normalized match key (lowercase)
    evidence_location: list[str]  # tool names that can surface this


@dataclass
class GroundTruth:
    case_id: str
    version: str
    iocs: list[GroundTruthIOC]


@dataclass
class ScoreResult:
    case_id: str
    agent_id: str
    gt_version: str
    run_id: str
    f1_applicable: float | None
    precision_applicable: float | None
    recall_applicable: float | None
    f1_total: float | None
    precision_total: float | None
    recall_total: float | None
    tp: int = 0
    fp: int = 0
    fn_applicable: int = 0
    applicable_count: int = 0
    total_count: int = 0
    found_ioc_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return dict(self.__dict__.items())


# ---------------------------------------------------------------------------
# Per-tool IOC extractors  →  normalized match keys
# ---------------------------------------------------------------------------


def _extract_psscan(rows: list[dict]) -> set[str]:
    found: set[str] = set()
    for r in rows:
        pid = r.get("PID") or r.get("pid") or r.get("Pid")
        name = r.get("ImageFileName") or r.get("image_file_name") or r.get("Name") or ""
        if pid is not None:
            found.add(f"{pid}:{str(name).lower().strip()}")
    return found


def _extract_netscan(rows: list[dict]) -> set[str]:
    found: set[str] = set()
    for r in rows:
        addr = r.get("ForeignAddr") or r.get("foreign_addr") or r.get("RemoteAddr") or ""
        port = r.get("ForeignPort") or r.get("foreign_port") or r.get("RemotePort") or ""
        if addr and str(addr) not in ("*", "0.0.0.0", "-", ""):
            found.add(f"{str(addr).lower()}:{port}")
    return found


def _extract_malfind(rows: list[dict]) -> set[str]:
    found: set[str] = set()
    for r in rows:
        pid = r.get("PID") or r.get("pid") or r.get("Pid")
        start = r.get("Start") or r.get("start") or r.get("VadStart") or ""
        if pid is not None:
            found.add(f"{pid}:{str(start).lower()}")
    return found


def _extract_registry(rows: list[dict]) -> set[str]:
    found: set[str] = set()
    for r in rows:
        key = r.get("Key") or r.get("key") or r.get("Hive") or ""
        name = r.get("Name") or r.get("name") or ""
        data = r.get("Data") or r.get("data") or ""
        if key:
            found.add(f"{str(key).lower()}:{str(name).lower()}")
        if data:
            found.add(f"data:{str(data).lower()[:128]}")
    return found


def _extract_mftscan(rows: list[dict]) -> set[str]:
    found: set[str] = set()
    for r in rows:
        fn = r.get("Filename") or r.get("filename") or r.get("FileName") or r.get("Name") or ""
        if fn:
            found.add(str(fn).lower().strip())
    return found


def _extract_mftscan_ads(rows: list[dict]) -> set[str]:
    found: set[str] = set()
    for r in rows:
        fn = r.get("Filename") or r.get("filename") or r.get("FileName") or ""
        ads = r.get("ADSFilename") or r.get("ads_filename") or r.get("ADS") or ""
        if fn:
            found.add(f"{str(fn).lower()}:{str(ads).lower()}")
    return found


def _extract_filescan(rows: list[dict]) -> set[str]:
    found: set[str] = set()
    for r in rows:
        fn = r.get("Name") or r.get("name") or r.get("Filename") or ""
        if fn:
            found.add(str(fn).lower().strip())
    return found


def _extract_cmdline(rows: list[dict]) -> set[str]:
    found: set[str] = set()
    for r in rows:
        pid = r.get("PID") or r.get("pid") or ""
        cmd = r.get("Args") or r.get("Cmd") or r.get("CommandLine") or ""
        if cmd:
            found.add(f"{pid}:{str(cmd).lower()[:128]}")
    return found


def _extract_dlllist(rows: list[dict]) -> set[str]:
    found: set[str] = set()
    for r in rows:
        dll = r.get("Base") or r.get("Name") or r.get("Path") or ""
        if dll:
            found.add(str(dll).lower().strip())
    return found


EXTRACTORS: dict[str, Callable[[list[dict]], set[str]]] = {
    "vol_pslist": _extract_psscan,
    "vol_psscan": _extract_psscan,
    "vol_netscan": _extract_netscan,
    "vol_malfind": _extract_malfind,
    "windows_psscan": _extract_psscan,
    "windows_netscan": _extract_netscan,
    "windows_malfind": _extract_malfind,
    "windows_registry_printkey": _extract_registry,
    "windows_mftscan": _extract_mftscan,
    "windows_mftscan_ads": _extract_mftscan_ads,
    "windows_filescan": _extract_filescan,
    "windows_cmdline": _extract_cmdline,
    "windows_dlllist": _extract_dlllist,
    "run_regripper": _extract_generic_text,
    "list_files": _extract_generic_text,
    "extract_file": _extract_generic_text,
    "filesystem_walk": _extract_generic_text,
    "mft_parse": _extract_generic_text,
    "registry_hive_parse": _extract_generic_text,
    "timeline_build": _extract_generic_text,
    "prefetch_parse": _extract_generic_text,
    "browser_history_parse": _extract_generic_text,
    "usn_journal_parse": _extract_generic_text,
    "lnk_file_parse": _extract_generic_text,
    "shellbag_parse": _extract_generic_text,
    "recycle_bin_parse": _extract_generic_text,
}


# ---------------------------------------------------------------------------
# Ground truth loader
# ---------------------------------------------------------------------------


def load_ground_truth(
    case_id: str,
    version: str,
    gt_root: Path = _GT_ROOT,
) -> GroundTruth:
    path = gt_root / f"{case_id}-v{version}.json"
    if not path.exists():
        raise FileNotFoundError(f"Ground truth not found: {path}")
    raw = json.loads(path.read_text())
    iocs = [
        GroundTruthIOC(
            ioc_id=ioc["ioc_id"],
            ioc_type=ioc["ioc_type"],
            value=str(ioc["value"]).lower().strip(),
            evidence_location=ioc.get("evidence_location", []),
        )
        for ioc in raw.get("iocs", [])
    ]
    return GroundTruth(case_id=raw["case_id"], version=raw["version"], iocs=iocs)


# ---------------------------------------------------------------------------
# Audit DB helpers
# ---------------------------------------------------------------------------


def _discover_output_column(cur: sqlite3.Cursor) -> str:
    cur.execute("PRAGMA table_info(auditentry)")
    cols = {row[1] for row in cur.fetchall()}
    for candidate in ("output_excerpt", "tool_output", "output", "result", "data"):
        if candidate in cols:
            return candidate
    raise RuntimeError(f"Cannot find tool output column in auditentry. Found: {cols}")


def extract_findings_from_db(
    audit_db_path: str | Path,
    run_id: str,
) -> set[str]:
    found_keys: set[str] = set()
    db_path = Path(audit_db_path)
    if not db_path.exists():
        return found_keys

    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.cursor()
        output_col = _discover_output_column(cur)

        tool_placeholders = ",".join("?" * len(IOC_PRODUCING_TOOLS))
        ",".join("?" * len(_TOOL_OUTPUT_EVENT_TYPES))

        # event_type column may not exist in older schemas — skip that filter
        cur.execute(
            f"SELECT tool_name, {output_col} FROM auditentry "
            f"WHERE run_id=? AND tool_name IN ({tool_placeholders}) "
            f"AND {output_col} IS NOT NULL",
            [run_id, *IOC_PRODUCING_TOOLS],
        )
        rows = cur.fetchall()

    for tool_name, raw_output in rows:
        extractor = EXTRACTORS.get(tool_name)
        if extractor is None or not raw_output:
            continue
        try:
            parsed = json.loads(raw_output)
            if isinstance(parsed, dict):
                for key in ("findings", "rows", "results", "data"):
                    if key in parsed:
                        parsed = parsed[key]
                        break
            elif isinstance(parsed, dict) and "findings" in parsed:
                parsed = parsed["findings"]
                parsed = parsed["rows"]
            if isinstance(parsed, list):
                found_keys.update(extractor(parsed))
        except (json.JSONDecodeError, TypeError):
            pass

    return found_keys


def get_last_run_id(
    audit_db_path: str | Path,
    agent_id: str,
    case_id: str,
) -> str | None:
    """Return most recent run_id for agent_id + case_id from audit DB."""
    db_path = Path(audit_db_path)
    if not db_path.exists():
        return None
    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(auditentry)")
        cols = {row[1] for row in cur.fetchall()}

        if "agent_id" in cols and "case_id" in cols:
            cur.execute(
                "SELECT run_id FROM auditentry WHERE agent_id=? AND case_id=? "
                "AND run_id IS NOT NULL ORDER BY rowid DESC LIMIT 1",
                (agent_id, case_id),
            )
        elif "agent_id" in cols:
            cur.execute(
                "SELECT run_id FROM auditentry WHERE agent_id=? "
                "AND run_id IS NOT NULL ORDER BY rowid DESC LIMIT 1",
                (agent_id,),
            )
        else:
            cur.execute(
                "SELECT run_id FROM auditentry WHERE run_id IS NOT NULL ORDER BY rowid DESC LIMIT 1"
            )
        row = cur.fetchone()
        return row[0] if row else None


# ---------------------------------------------------------------------------
# F1 helpers
# ---------------------------------------------------------------------------


def _prf(tp: int, fp: int, fn: int) -> tuple[float | None, float | None, float | None]:
    p = tp / (tp + fp) if (tp + fp) > 0 else None
    r = tp / (tp + fn) if (tp + fn) > 0 else None
    f1 = (
        (2 * p * r / (p + r))
        if (p is not None and r is not None and p + r > 0)
        else (0.0 if (p is not None and r is not None) else None)
    )
    return p, r, f1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_run(
    case_id: str,
    agent_id: str,
    gt_version: str,
    audit_db_path: str | Path,
    run_id: str,
    gt_root: Path = _GT_ROOT,
) -> ScoreResult:
    gt = load_ground_truth(case_id, gt_version, gt_root)
    found_keys = extract_findings_from_db(audit_db_path, run_id)

    applicable = [
        ioc for ioc in gt.iocs if any(loc in IOC_PRODUCING_TOOLS for loc in ioc.evidence_location)
    ]

    # Applicable F1
    if not applicable:
        f1_app = prec_app = rec_app = None
        tp = fp = fn_app = 0
    else:
        app_vals = {ioc.value for ioc in applicable}
        tp = len(found_keys & app_vals)
        fp = len(found_keys - app_vals)
        fn_app = len(app_vals - found_keys)
        prec_app, rec_app, f1_app = _prf(tp, fp, fn_app)

    # Total F1
    if not gt.iocs:
        f1_tot = prec_tot = rec_tot = None
    else:
        all_vals = {ioc.value for ioc in gt.iocs}
        tp_t = len(found_keys & all_vals)
        fp_t = len(found_keys - all_vals)
        fn_t = len(all_vals - found_keys)
        prec_tot, rec_tot, f1_tot = _prf(tp_t, fp_t, fn_t)

    return ScoreResult(
        case_id=case_id,
        agent_id=agent_id,
        gt_version=gt_version,
        run_id=run_id,
        f1_applicable=f1_app,
        precision_applicable=prec_app,
        recall_applicable=rec_app,
        f1_total=f1_tot,
        precision_total=prec_tot,
        recall_total=rec_tot,
        tp=tp,
        fp=fp,
        fn_applicable=fn_app,
        applicable_count=len(applicable),
        total_count=len(gt.iocs),
        found_ioc_keys=sorted(found_keys),
    )


def score_run_from_report(
    case_id: str,
    agent_id: str,
    gt_version: str,
    report_text: str,
    gt_root: Path = _GT_ROOT,
) -> ScoreResult:
    """Degraded path for runs without run_id. Recall only; precision=None."""
    gt = load_ground_truth(case_id, gt_version, gt_root)
    report_lower = report_text.lower()
    applicable = [
        ioc for ioc in gt.iocs if any(loc in IOC_PRODUCING_TOOLS for loc in ioc.evidence_location)
    ]
    if not applicable:
        return ScoreResult(
            case_id=case_id,
            agent_id=agent_id,
            gt_version=gt_version,
            run_id="<report>",
            f1_applicable=None,
            precision_applicable=None,
            recall_applicable=None,
            f1_total=None,
            precision_total=None,
            recall_total=None,
            applicable_count=0,
            total_count=len(gt.iocs),
        )
    hits = {ioc.value for ioc in applicable if ioc.value in report_lower}
    tp = len(hits)
    fn = len(applicable) - tp
    recall = tp / len(applicable)
    return ScoreResult(
        case_id=case_id,
        agent_id=agent_id,
        gt_version=gt_version,
        run_id="<report>",
        f1_applicable=None,
        precision_applicable=None,
        recall_applicable=recall,
        f1_total=None,
        precision_total=None,
        recall_total=None,
        tp=tp,
        fp=0,
        fn_applicable=fn,
        applicable_count=len(applicable),
        total_count=len(gt.iocs),
        found_ioc_keys=sorted(hits),
    )
