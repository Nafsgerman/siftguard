"""
SIFTGuard Spoliation Test Suite
================================
Proves that evidence destruction is architecturally impossible.
Each test ATTEMPTS a destructive action and verifies it is BLOCKED.
This is not a safety feature — it is an architectural guarantee.
"""

from __future__ import annotations

import pytest

from siftguard.mcp_server.safe_exec import SafeExecError, safe_exec

# ── Attack 1: Direct rm command ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rm_binary_blocked():
    """rm is not in the allowlist — cannot be called."""
    with pytest.raises(SafeExecError, match="not in allowlist"):
        await safe_exec("rm", ["-rf", "/cases/TEST-001/base-hunt-memory.img"])


# ── Attack 2: rm via shell injection in args ──────────────────────────────────


@pytest.mark.asyncio
async def test_rm_pattern_in_args_blocked():
    """rm pattern in args is blocked by deny list."""
    with pytest.raises(SafeExecError, match="denied pattern"):
        await safe_exec("fls", ["-r", "/cases/evidence.E01", "; rm -rf /cases"])


# ── Attack 3: dd (disk wipe) ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dd_wipe_blocked():
    """dd is not in the allowlist."""
    with pytest.raises(SafeExecError, match="not in allowlist"):
        await safe_exec("dd", ["if=/dev/zero", "of=/cases/TEST-001/base-hunt-memory.img"])


# ── Attack 4: dd pattern in args ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dd_pattern_in_args_blocked():
    """dd of= pattern blocked even inside allowed binary args."""
    with pytest.raises(SafeExecError, match="denied pattern"):
        await safe_exec("fls", ["/cases/evidence.E01", "dd of=/dev/sda"])


# ── Attack 5: mkfs (format filesystem) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_mkfs_blocked():
    """mkfs is not in the allowlist."""
    with pytest.raises(SafeExecError, match="not in allowlist"):
        await safe_exec("mkfs.ext4", ["/dev/sda1"])


# ── Attack 6: Path traversal outside evidence root ───────────────────────────


@pytest.mark.asyncio
async def test_path_traversal_blocked():
    """Paths escaping the evidence root are blocked."""
    with pytest.raises(SafeExecError, match="path escapes evidence root"):
        await safe_exec("fls", ["/etc/passwd"])


# ── Attack 7: shutdown ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_shutdown_blocked():
    """shutdown is not in the allowlist."""
    with pytest.raises(SafeExecError, match="not in allowlist"):
        await safe_exec("shutdown", ["now"])


# ── Attack 8: Redirect to overwrite evidence ─────────────────────────────────


@pytest.mark.asyncio
async def test_redirect_overwrite_blocked():
    """Shell redirect pattern > / is blocked."""
    with pytest.raises(SafeExecError, match="denied pattern"):
        await safe_exec("fls", ["/cases/evidence.E01", "> /cases/evidence.E01"])


# ── Attack 9: kill process ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_kill_blocked():
    """kill is not in the allowlist."""
    with pytest.raises(SafeExecError, match="not in allowlist"):
        await safe_exec("kill", ["-9", "1"])


# ── Attack 10: chmod to make evidence writable ───────────────────────────────


@pytest.mark.asyncio
async def test_chmod_write_blocked():
    """chmod +w pattern is blocked."""
    with pytest.raises(SafeExecError, match="denied pattern"):
        await safe_exec("fls", ["chmod +w /cases/evidence.E01"])


# ── Positive: legitimate forensic call passes validation ─────────────────────


@pytest.mark.asyncio
async def test_legitimate_fls_passes_validation():
    """A legitimate fls call passes safe_exec validation (even if binary missing)."""
    try:
        await safe_exec("fls", ["-r", "/cases/TEST-001/base-hunt-memory.img"])
    except SafeExecError as e:
        # Only acceptable failure: binary not found (not in path on Mac)
        # NOT acceptable: allowlist rejection or deny pattern match
        assert "not in allowlist" not in str(e)
        assert "denied pattern" not in str(e)
        assert "path escapes" not in str(e)
    except FileNotFoundError:
        pass  # Binary not installed on Mac — expected, not a spoliation failure


@pytest.mark.asyncio
async def test_legitimate_vol3_passes_validation():
    """A legitimate vol3 call passes safe_exec validation."""
    try:
        await safe_exec(
            "/opt/volatility3/bin/vol",
            ["-f", "/cases/TEST-001/base-hunt-memory.img", "-r", "jsonl", "windows.psscan"],
        )
    except SafeExecError as e:
        assert "not in allowlist" not in str(e)
        assert "denied pattern" not in str(e)
        assert "path escapes" not in str(e)
    except FileNotFoundError:
        pass


# ── Attack 13-15: Relative traversal (P0-A, added post-T22) ──────────────────


@pytest.mark.asyncio
async def test_relative_traversal_dotdot_blocked():
    """../../ prefix must be caught even though it does not start with / or ./"""
    with pytest.raises(SafeExecError, match="path escapes evidence root"):
        await safe_exec("fls", ["../../etc/passwd"])


@pytest.mark.asyncio
async def test_relative_traversal_in_middle_blocked():
    """Traversal embedded after a valid-looking prefix is blocked."""
    with pytest.raises(SafeExecError, match="path escapes evidence root"):
        await safe_exec("fls", ["cases/../../../etc/shadow"])


@pytest.mark.asyncio
async def test_relative_traversal_after_flag_blocked():
    """Traversal as a positional arg after a flag is blocked."""
    with pytest.raises(SafeExecError, match="path escapes evidence root"):
        await safe_exec("fls", ["-r", "../../etc/passwd"])
