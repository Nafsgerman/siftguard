from __future__ import annotations

import asyncio
import os
import shlex
import time
from dataclasses import dataclass
from pathlib import Path

# REPLACE
ALLOWED_BINARIES: set[str] = {
    "analyzeMFT.py",
    "mft_dump",
    "log2timeline.py",
    "psort.py",
    "/opt/volatility3/bin/vol",
    "bulk_extractor",
    "regripper",
    "rip.pl",
    "/usr/local/bin/rip.pl",
    "fls",
    "/usr/bin/fls",
    "icat",
    "/usr/bin/icat",
    "mmls",
    "/usr/bin/mmls",
    "fsstat",
    "/usr/bin/fsstat",
    "tsk_recover",
    "evtxexport",
}

DENY_PATTERNS: set[str] = {
    "rm ",
    "rm\t",
    "mkfs",
    "dd if=",
    "dd of=",
    " > /",
    ">/dev/",
    "shutdown",
    "reboot",
    "iptables",
    "kill ",
    "pkill",
    "chmod +w",
    "chown ",
}


@dataclass
class ExecResult:
    stdout: str
    stderr: str
    returncode: int
    duration_ms: int


class SafeExecError(Exception):
    pass


async def safe_exec(
    binary: str,
    args: list[str],
    *,
    cwd: str | None = None,
    timeout_s: int = 120,
    env: dict[str, str] | None = None,
) -> ExecResult:
    if binary not in ALLOWED_BINARIES:
        raise SafeExecError(f"binary not in allowlist: {binary}")

    cmdline = " ".join([binary, *args])
    for pat in DENY_PATTERNS:
        if pat in cmdline:
            raise SafeExecError(f"denied pattern in command: {pat!r}")

    evidence_root = Path(os.environ.get("SIFTGUARD_EVIDENCE_ROOT", "/cases")).resolve()
    safe_prefixes = ("/usr/", "/opt/", "/home/sansforensics/", "/tmp/", "/cases/")
    for a in args:
        if a.startswith("-"):
            continue
        if "/" in a or a.startswith(".."):
            try:
                resolved = (
                    Path(a).resolve() if Path(a).is_absolute() else (evidence_root / a).resolve()
                )
                if (
                    evidence_root not in resolved.parents
                    and resolved != evidence_root
                    and not any(str(resolved).startswith(p) for p in safe_prefixes)
                ):
                    raise SafeExecError(f"path escapes evidence root: {a}")
            except (OSError, ValueError):
                pass

    full_env = {**os.environ, **(env or {})}
    start = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        binary,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=full_env,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        raise SafeExecError(f"timeout after {timeout_s}s: {binary} {shlex.join(args)}") from None

    return ExecResult(
        stdout=stdout_b.decode(errors="replace"),
        stderr=stderr_b.decode(errors="replace"),
        returncode=proc.returncode if proc.returncode is not None else -1,
        duration_ms=int((time.monotonic() - start) * 1000),
    )
