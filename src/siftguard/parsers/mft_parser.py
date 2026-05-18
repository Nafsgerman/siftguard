from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from siftguard.models.forensic import MFTEntry


def _parse_dt(s: str) -> datetime | None:
    if not s or s in {"N/A", ""}:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def parse_analyze_mft_csv(path: str | Path) -> list[MFTEntry]:
    entries: list[MFTEntry] = []
    p = Path(path)
    if not p.exists():
        return entries
    with p.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            si_c = _parse_dt(row.get("SI Creation", ""))
            si_m = _parse_dt(row.get("SI Modification", ""))
            fn_c = _parse_dt(row.get("FN Creation", ""))
            fn_m = _parse_dt(row.get("FN Modification", ""))
            timestomp = bool((si_c and fn_c and si_c < fn_c) or (si_m and fn_m and si_m < fn_m))
            try:
                entries.append(
                    MFTEntry(
                        record_number=int(row.get("Record Number", 0)),
                        in_use=row.get("Active", "").lower() == "active",
                        file_type="Directory"
                        if "Directory" in row.get("Record type", "")
                        else "File",
                        full_path=row.get("Filename #1", ""),
                        file_size=int(row.get("Filesize", 0) or 0),
                        si_created=si_c,
                        si_modified=si_m,
                        si_accessed=_parse_dt(row.get("SI Access", "")),
                        si_entry_modified=_parse_dt(row.get("SI Entry", "")),
                        fn_created=fn_c,
                        fn_modified=fn_m,
                        timestomp_suspected=timestomp,
                    )
                )
            except (ValueError, TypeError):
                continue
    return entries
