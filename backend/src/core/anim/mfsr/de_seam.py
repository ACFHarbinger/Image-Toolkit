"""
Differential Evolution (DE) for optimal seam finding in stitched overlaps.

Encodes seam paths as real-valued chromosomes and evolves them to minimize:
  E(seam) = sum data_cost(p) + lambda * sum smoothness_cost(p, q)

Outperforms DP seam finding on complex textures and moving elements.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..constants import DE_CR, DE_F, DE_MAX_GEN, DE_POP_SIZE
from ..utils import _seam_dp


def _energy_map(img_a: np.ndarray, img_b: np.ndarray) -> np.ndarray:
    """Per-pixel energy: |a - b| + gradient magnitude."""
    diff = cv2.absdiff(img_a, img_b).astype(np.float32).mean(axis=2)
    gx = cv2.Sobel(diff, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(diff, cv2.CV_32F, 0, 1, ksize=3)
    return diff + 0.5 * (np.abs(gx) + np.abs(gy))


def _seam_energy(
    path: np.ndarray,
    energy: np.ndarray,
    smoothness_weight: float = 0.5,
) -> float:
    """
    Evaluate the energy of a seam path on the energy map.

    `path` is a 1D int array of column-per-row (after orientation has been
    normalised so the seam runs across the first axis of `energy`).
    """
    h, w = energy.shape
    path = np.clip(path.astype(np.int32), 0, w - 1)
    rows = np.arange(h)
    data = energy[rows, path].sum()
    # Smoothness: |p[i+1] - p[i]| should be small (seam doesn't zig-zag).
    diffs = np.abs(np.diff(path))
    smooth = float(diffs.sum())
    return float(data + smoothness_weight * smooth)


def de_seam(
    img_a: np.ndarray,
    img_b: np.ndarray,
    horizontal: bool = True,
    pop_size: int = DE_POP_SIZE,
    n_gen: int = DE_MAX_GEN,
    smoothness_weight: float = 0.5,
) -> np.ndarray:
    """
    DE-optimized seam path.  Returns int array (same shape/orientation as
    :func:`_seam_dp` would return).  Falls back to DP seam if DE yields a
    higher energy than the DP baseline.
    """
    if img_a.shape != img_b.shape:
        raise ValueError("de_seam: img_a and img_b must have the same shape")

    energy = _energy_map(img_a, img_b)
    if not horizontal:
        energy = energy.T
    h, w = energy.shape

    # Baseline DP seam (also used to seed half the population).
    dp_path = _seam_dp(img_a, img_b, horizontal=horizontal).astype(np.float64)
    if not horizontal:
        # `_seam_dp` returns path along the (post-transpose) row axis already.
        pass
    dp_path = np.clip(dp_path, 0, w - 1)
    dp_energy = _seam_energy(dp_path.astype(np.int32), energy, smoothness_weight)

    rng = np.random.default_rng(0)
    # Initial population: half jittered DP paths, half random monotone-ish.
    pop = np.empty((pop_size, h), dtype=np.float64)
    n_dp = pop_size // 2
    for k in range(n_dp):
        jitter = rng.normal(0.0, max(1.0, w * 0.01), size=h)
        pop[k] = dp_path + jitter
    for k in range(n_dp, pop_size):
        # Random walks bounded by [0, w)
        start = rng.uniform(0, w - 1)
        steps = rng.normal(0.0, 1.0, size=h - 1)
        walk = np.concatenate([[start], steps]).cumsum()
        walk -= walk.min()
        walk *= (w - 1) / (walk.max() + 1e-6)
        pop[k] = walk

    pop = np.clip(pop, 0, w - 1)

    fitness = np.array(
        [_seam_energy(p.astype(np.int32), energy, smoothness_weight) for p in pop],
        dtype=np.float64,
    )

    for gen in range(n_gen):
        for i in range(pop_size):
            # Sample three distinct random indices != i
            idxs = list(range(pop_size))
            idxs.remove(i)
            a, b, c = rng.choice(idxs, size=3, replace=False)

            mutant = pop[a] + DE_F * (pop[b] - pop[c])
            mutant = np.clip(mutant, 0, w - 1)

            # Binomial crossover
            cross = rng.random(h) < DE_CR
            if not cross.any():
                cross[rng.integers(0, h)] = True
            trial = np.where(cross, mutant, pop[i])

            trial_fit = _seam_energy(trial.astype(np.int32), energy, smoothness_weight)
            if trial_fit < fitness[i]:
                pop[i] = trial
                fitness[i] = trial_fit

    best = int(np.argmin(fitness))
    de_path = pop[best].astype(np.int32)
    de_path = np.clip(de_path, 0, w - 1)

    if fitness[best] < dp_energy:
        return de_path
    # DP wins — fall back.
    return _seam_dp(img_a, img_b, horizontal=horizontal)


__all__ = ["de_seam"]
