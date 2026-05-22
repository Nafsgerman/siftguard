"""Tests for _cache_dir path resolution and failure handling."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from siftguard.mcp_server.tools.volatility import _cache_dir


def test_env_var_override(tmp_path):
    override = str(tmp_path / "custom_cache")
    with patch.dict(os.environ, {"SIFTGUARD_CACHE_DIR": override}):
        result = _cache_dir("/cases/TEST-001/memory.img")
    assert result == Path(override)
    assert result.exists()


def test_image_relative_default(tmp_path):
    img = tmp_path / "memory.img"
    img.touch()
    result = _cache_dir(str(img))
    assert result == tmp_path / "siftguard_cache"
    assert result.exists()


def test_readonly_raises_clean_error(tmp_path):
    readonly = tmp_path / "ro"
    readonly.mkdir()
    readonly.chmod(0o444)
    img = readonly / "memory.img"
    with pytest.raises(RuntimeError, match="not writable"):
        _cache_dir(str(img))
    readonly.chmod(0o755)  # cleanup


def test_env_var_created_if_missing(tmp_path):
    deep = str(tmp_path / "a" / "b" / "c")
    with patch.dict(os.environ, {"SIFTGUARD_CACHE_DIR": deep}):
        result = _cache_dir("/any/path.img")
    assert Path(deep).exists()
    assert result == Path(deep)
