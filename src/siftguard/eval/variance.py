"""Bootstrap confidence intervals for ablation seed repeats.

Usage:
    from siftguard.eval.variance import compute_variance_stats
    stats = compute_variance_stats([0.72, 0.74, 0.71])
    # VarianceStats(n=3, mean=0.723, std=0.015, ci_lower=0.71, ci_upper=0.74, ci_level=0.95)
"""
from __future__ import annotations

import math
import random
from typing import Sequence

from pydantic import BaseModel


class VarianceStats(BaseModel):
    n: int
    mean: float
    std: float
    ci_lower: float
    ci_upper: float
    ci_level: float = 0.95

    model_config = {"frozen": True}

    @property
    def margin(self) -> float:
        return (self.ci_upper - self.ci_lower) / 2

    def __str__(self) -> str:
        return (
            f"{self.mean:.3f} ± {self.std:.3f} "
            f"[{self.ci_lower:.3f}, {self.ci_upper:.3f}] "
            f"(n={self.n}, {int(self.ci_level * 100)}% CI)"
        )


def bootstrap_ci(
    scores: Sequence[float],
    n_resamples: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean. Returns (lower, upper)."""
    scores_list = list(scores)
    n = len(scores_list)
    if n == 0:
        return (0.0, 0.0)
    if n == 1:
        return (scores_list[0], scores_list[0])

    rng = random.Random(seed)
    boot_means: list[float] = sorted(
        sum(rng.choices(scores_list, k=n)) / n
        for _ in range(n_resamples)
    )
    alpha = (1.0 - ci) / 2
    lo = boot_means[max(0, int(alpha * n_resamples))]
    hi = boot_means[min(n_resamples - 1, int((1 - alpha) * n_resamples) - 1)]
    return (lo, hi)


def compute_variance_stats(
    scores: Sequence[float],
    n_resamples: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> VarianceStats:
    scores_list = list(scores)
    n = len(scores_list)
    if n == 0:
        return VarianceStats(n=0, mean=0.0, std=0.0, ci_lower=0.0, ci_upper=0.0, ci_level=ci)
    mean = sum(scores_list) / n
    if n == 1:
        return VarianceStats(n=1, mean=round(mean, 6), std=0.0,
                             ci_lower=round(mean, 6), ci_upper=round(mean, 6), ci_level=ci)
    std = math.sqrt(sum((s - mean) ** 2 for s in scores_list) / (n - 1))
    lo, hi = bootstrap_ci(scores_list, n_resamples=n_resamples, ci=ci, seed=seed)
    return VarianceStats(
        n=n,
        mean=round(mean, 6),
        std=round(std, 6),
        ci_lower=round(lo, 6),
        ci_upper=round(hi, 6),
        ci_level=ci,
    )