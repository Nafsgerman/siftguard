"""Tests for panel_6b_stability — does not require real seed run data."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
from unittest.mock import patch

import matplotlib.pyplot as plt


def _make_ax():
    fig, ax = plt.subplots()
    return ax


def test_placeholder_when_no_runs():
    from siftguard.eval.analytics import panel_6b_stability

    ax = _make_ax()
    with patch("siftguard.eval.ablation_runner.load_seed_results", return_value=[]):
        result = panel_6b_stability.render(ax, case_id="TEST-001")
    assert result["status"] == "placeholder"
    plt.close("all")


def test_sigma_style_stable():
    from siftguard.eval.analytics.panel_6b_stability import _sigma_style

    color, lw, warn = _sigma_style(0.01)
    assert warn == ""
    assert lw < 2.0


def test_sigma_style_warn():
    from siftguard.eval.analytics.panel_6b_stability import _sigma_style

    color, lw, warn = _sigma_style(0.03)
    assert warn == ""
    assert lw >= 2.0


def test_sigma_style_bad():
    from siftguard.eval.analytics.panel_6b_stability import RED, _sigma_style

    color, lw, warn = _sigma_style(0.06)
    assert color == RED
    assert "⚠" in warn
    assert lw >= 3.0


def test_claim_string():
    from siftguard.eval.analytics.panel_6b_stability import CLAIM

    assert "reproducible" in CLAIM
    assert "lucky" in CLAIM
