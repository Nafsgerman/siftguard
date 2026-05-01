from __future__ import annotations
import json
from siftguard.models.forensic import VolatilityProcess

SUSPICIOUS_PROCESS_NAMES = {
    "cmd.exe", "powershell.exe", "wscript.exe", "cscript.exe",
    "mshta.exe", "regsvr32.exe", "rundll32.exe", "schtasks.exe",
    "certutil.exe", "bitsadmin.exe", "msiexec.exe",
}

SUSPICIOUS_PARENT_COMBOS = {
    ("word.exe", "cmd.exe"),
    ("excel.exe", "powershell.exe"),
    ("outlook.exe", "cmd.exe"),
    ("explorer.exe", "svchost.exe"),
}


def _flag_process(name: str, ppid: int, all_procs: dict[int, str]) -> list[str]:
    flags = []
    parent_name = all_procs.get(ppid, "").lower()
    name_lower = name.lower()
    if name_lower in SUSPICIOUS_PROCESS_NAMES:
        flags.append(f"suspicious_binary:{name}")
    if (parent_name, name_lower) in SUSPICIOUS_PARENT_COMBOS:
        flags.append(f"suspicious_parent_child:{parent_name}->{name_lower}")
    return flags


def parse_pslist(raw: str) -> list[VolatilityProcess]:
    processes: list[VolatilityProcess] = []
    pid_name_map: dict[int, str] = {}

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("Volatility") or line.startswith("Progress"):
            continue
        try:
            row = json.loads(line)
            pid = int(row.get("PID", 0))
            name = row.get("ImageFileName", "")
            pid_name_map[pid] = name
        except (json.JSONDecodeError, ValueError):
            continue

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("Volatility") or line.startswith("Progress"):
            continue
        try:
            row = json.loads(line)
            pid = int(row.get("PID", 0))
            ppid = int(row.get("PPID", 0))
            name = row.get("ImageFileName", "")
            processes.append(VolatilityProcess(
                pid=pid, ppid=ppid, name=name,
                create_time=None, exit_time=None,
                threads=int(row.get("Threads", 0) or 0),
                handles=None,
                suspicious_indicators=_flag_process(name, ppid, pid_name_map),
            ))
        except (json.JSONDecodeError, ValueError):
            continue
    return processes


def parse_netscan(raw: str) -> list[dict]:
    results = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("Volatility") or line.startswith("Progress"):
            continue
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return results


def parse_malfind(raw: str) -> list[dict]:
    results = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("Volatility") or line.startswith("Progress"):
            continue
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return results