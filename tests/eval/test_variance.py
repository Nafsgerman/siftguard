"""Tests for siftguard.eval.variance."""

from __future__ import annotations

from siftguard.eval.variance import bootstrap_ci, compute_variance_stats


def test_empty_scores():
    stats = compute_variance_stats([])
    assert stats.n == 0
    assert stats.mean == 0.0
    assert stats.ci_lower == 0.0


def test_single_score():
    stats = compute_variance_stats([0.75])
    assert stats.n == 1
    assert stats.mean == 0.75
    assert stats.std == 0.0
    assert stats.ci_lower == stats.ci_upper == 0.75


def test_identical_scores():
    stats = compute_variance_stats([0.8, 0.8, 0.8])
    assert stats.n == 3
    assert abs(stats.mean - 0.8) < 1e-6
    assert stats.std == 0.0


def test_two_scores():
    stats = compute_variance_stats([0.70, 0.80])
    assert stats.n == 2
    assert abs(stats.mean - 0.75) < 1e-6
    assert stats.ci_lower <= stats.mean <= stats.ci_upper


def test_three_seeds_typical():
    stats = compute_variance_stats([0.706, 0.712, 0.698])
    assert stats.n == 3
    assert 0.69 < stats.mean < 0.72
    assert stats.std > 0
    assert stats.ci_lower <= stats.mean <= stats.ci_upper


def test_ci_width_shrinks_with_identical():
    stats = compute_variance_stats([0.5, 0.5, 0.5, 0.5, 0.5])
    assert stats.margin < 0.01


def test_bootstrap_ci_empty():
    assert bootstrap_ci([]) == (0.0, 0.0)


def test_bootstrap_ci_single():
    assert bootstrap_ci([0.9]) == (0.9, 0.9)


def test_bootstrap_ci_ordering():
    lo, hi = bootstrap_ci([0.6, 0.8, 0.7], seed=0)
    assert lo <= hi


def test_variance_stats_str():
    stats = compute_variance_stats([0.72, 0.74, 0.71])
    s = str(stats)
    assert "±" in s
    assert "95% CI" in s


def test_margin_property():
    stats = compute_variance_stats([0.70, 0.80])
    assert abs(stats.margin - (stats.ci_upper - stats.ci_lower) / 2) < 1e-9
