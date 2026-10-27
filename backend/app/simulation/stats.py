"""Interval estimates for simulator counts.

These quantify Monte Carlo sampling uncertainty only: how much the counts would
move with more rollouts of the same model. They say nothing about whether the
model represents football well.
"""

from __future__ import annotations

import math

import numpy as np


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a single binomial rate."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def paired_bootstrap(a: np.ndarray, b: np.ndarray, n_boot: int = 2000, seed: int = 0) -> tuple[float, tuple[float, float]]:
    """Mean of (b - a) over paired trials and its 95% percentile bootstrap interval.

    Trials are resampled as pairs, so the shared random conditions of trial r
    stay matched between the two arms.
    """
    d = b.astype(float) - a.astype(float)
    if d.size == 0:
        return 0.0, (0.0, 0.0)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(n_boot, d.size))
    means = d[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(d.mean()), (float(lo), float(hi))
