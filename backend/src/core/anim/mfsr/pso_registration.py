"""
Particle Swarm Optimization (PSO) for image pair geometric registration.

Replaces or augments Levenberg-Marquardt bundle adjustment for pairs
where gradient-based methods fail (uniform textures, repetitive patterns).

Each particle represents a candidate transformation [dx, dy] (translation)
or [dx, dy, da, db] (partial affine, 4-DOF).

Fitness function: Normalized Cross-Correlation between warped source and
reference image (background-masked).
"""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

from ..constants import (
    PSO_C1,
    PSO_C2,
    PSO_INERTIA,
    PSO_MAX_ITER,
    PSO_SWARM_SIZE,
    PSO_VEL_CLAMP,
)


def _ncc(
    a: np.ndarray,
    b: np.ndarray,
    mask: Optional[np.ndarray] = None,
) -> float:
    """Normalized cross-correlation between two same-shaped 2D images."""
    af = a.astype(np.float64)
    bf = b.astype(np.float64)
    if mask is not None:
        m = (mask > 0).astype(np.float64)
        af = af * m
        bf = bf * m
        n = max(float(m.sum()), 1.0)
    else:
        n = af.size

    ma = af.sum() / n
    mb = bf.sum() / n
    da = af - ma
    db = bf - mb
    num = float((da * db).sum())
    den = float(np.sqrt((da * da).sum() * (db * db).sum()) + 1e-9)
    return num / den


def _params_to_M(params: np.ndarray, motion_model: str) -> np.ndarray:
    """Convert PSO parameter vector to a (2,3) affine matrix."""
    if motion_model == "translation":
        dx, dy = float(params[0]), float(params[1])
        return np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    # 4-DOF partial affine: a, b, dx, dy   ->   M = [[a, b, dx], [-b, a, dy]]
    a, b, dx, dy = (float(params[k]) for k in range(4))
    return np.array([[a, b, dx], [-b, a, dy]], dtype=np.float32)


def _warp(src: np.ndarray, M: np.ndarray, h: int, w: int) -> np.ndarray:
    return cv2.warpAffine(
        src,
        M,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def pso_register(
    img_ref: np.ndarray,
    img_src: np.ndarray,
    mask_ref: Optional[np.ndarray] = None,
    mask_src: Optional[np.ndarray] = None,
    search_range: Tuple[float, float] = (-500.0, 500.0),
    motion_model: str = "translation",
    n_particles: int = PSO_SWARM_SIZE,
    n_iter: int = PSO_MAX_ITER,
    init_guess: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, float]:
    """
    PSO registration returning ((2,3) affine matrix, confidence score in [-1,1]).

    Particles are initialised near ``init_guess`` (if given) or uniformly within
    ``search_range``.  Fitness = NCC between the warped source and the
    reference, optionally masked by ``mask_ref``.
    """
    if img_ref.ndim == 3:
        ref_g = cv2.cvtColor(img_ref, cv2.COLOR_BGR2GRAY)
    else:
        ref_g = img_ref
    if img_src.ndim == 3:
        src_g = cv2.cvtColor(img_src, cv2.COLOR_BGR2GRAY)
    else:
        src_g = img_src

    h, w = ref_g.shape[:2]
    lo, hi = float(search_range[0]), float(search_range[1])

    if motion_model == "translation":
        dim = 2
        bounds_lo = np.array([lo, lo], dtype=np.float64)
        bounds_hi = np.array([hi, hi], dtype=np.float64)
    else:
        dim = 4
        # a,b bounds keep scale within [0.85, 1.15] and rotation small
        bounds_lo = np.array([0.85, -0.15, lo, lo], dtype=np.float64)
        bounds_hi = np.array([1.15, 0.15, hi, hi], dtype=np.float64)

    rng = np.random.default_rng(0)
    pos = rng.uniform(bounds_lo, bounds_hi, size=(n_particles, dim))
    if init_guess is not None:
        guess = np.asarray(init_guess, dtype=np.float64).reshape(-1)
        if guess.size == dim:
            pos[0] = guess
            # Cluster a few particles tightly around the initial guess for
            # fast convergence.
            jitter = (bounds_hi - bounds_lo) * 0.02
            pos[1 : min(8, n_particles)] = guess + rng.normal(
                0.0, jitter, size=(min(8, n_particles) - 1, dim)
            )

    vel_range = (bounds_hi - bounds_lo) * PSO_VEL_CLAMP
    vel = rng.uniform(-vel_range, vel_range, size=(n_particles, dim))

    def fitness(p: np.ndarray) -> float:
        M = _params_to_M(p, motion_model)
        warped = _warp(src_g, M, h, w)
        if mask_ref is not None:
            return _ncc(warped, ref_g, mask=mask_ref)
        return _ncc(warped, ref_g)

    pbest_pos = pos.copy()
    pbest_val = np.array([fitness(p) for p in pos], dtype=np.float64)
    gbest_idx = int(np.argmax(pbest_val))
    gbest_pos = pbest_pos[gbest_idx].copy()
    gbest_val = float(pbest_val[gbest_idx])

    for it in range(n_iter):
        r1 = rng.uniform(0.0, 1.0, size=(n_particles, dim))
        r2 = rng.uniform(0.0, 1.0, size=(n_particles, dim))
        vel = (
            PSO_INERTIA * vel
            + PSO_C1 * r1 * (pbest_pos - pos)
            + PSO_C2 * r2 * (gbest_pos[None, :] - pos)
        )
        # Velocity clamp
        vel = np.clip(vel, -vel_range, vel_range)
        pos = pos + vel
        # Reflect at bounds
        below = pos < bounds_lo
        above = pos > bounds_hi
        pos[below] = bounds_lo[np.where(below)[1]] if dim == 1 else np.where(
            below, np.broadcast_to(bounds_lo, pos.shape), pos
        )[below]
        pos[above] = np.where(
            above, np.broadcast_to(bounds_hi, pos.shape), pos
        )[above]
        vel[below] *= -0.5
        vel[above] *= -0.5

        for k in range(n_particles):
            f = fitness(pos[k])
            if f > pbest_val[k]:
                pbest_val[k] = f
                pbest_pos[k] = pos[k]
                if f > gbest_val:
                    gbest_val = f
                    gbest_pos = pos[k].copy()

        # Early stop if converged.
        if gbest_val > 0.995:
            break

    return _params_to_M(gbest_pos, motion_model), float(gbest_val)


__all__ = ["pso_register"]
