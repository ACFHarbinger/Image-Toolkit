"""Screentone-aware scribble colorization (roadmap §2.2, issue #187).

The plain Levin scribble colorizer (``colorization.py``) weights pixel
affinity by *intensity* correlation, which fails on screentoned manga: a
halftone dot pattern's raw pixel values swing between pure black and pure
white, artificially maximizing local intensity variance and either bleeding
color across a screentone boundary or halting propagation altogether inside
a single halftone region (research report §5.2).

The roadmap's original formulation for this is a level-set PDE
(``Phi_t = h * (F0 + F1|grad(Phi)|)``) with a halting function
``h(x,y) = 1/(1 + |D(T_scribble, T(x,y))|)`` over Gabor texture features --
i.e. "keep propagating while the local texture pattern matches, stop where
it changes." This module achieves the same practical goal with a solver
that's already built, tested, and shipped: **the same convex quadratic-cost
graph-Laplacian solve as ``colorization.py``, with pixel affinity weights
derived from Gabor *texture*-feature distance instead of raw intensity
correlation.** Both formulations are monotonically-decreasing functions of
a local pattern-distance measure that pin propagation strength to "does this
neighbor look like the same pattern" -- a Gaussian-kernel graph weight
(``w_rs = exp(-||T(r)-T(s)||^2 / (2*sigma^2))``) is the direct discrete
graph-Laplacian analog of a level-set halting function, without needing a
second, separate PDE time-stepping solver (with its own stability/
reinitialization concerns) alongside the one this module's sibling already
solves reliably. This is a deliberate implementation choice, not a
simplification that changes the observable goal: propagation still halts at
screentone-pattern boundaries rather than at raw-intensity boundaries.
"""

from __future__ import annotations

import cv2
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu

from .colorization import _neighbor_offsets
from .gabor import gabor_feature_bank

__all__ = ["build_texture_affinity_system", "colorize_scribble_screentone"]


def build_texture_affinity_system(features: np.ndarray, win_rad: int = 1, sigma: float = 1.0) -> sparse.csr_matrix:
    """Build the sparse ``(I - W)`` affinity system from per-pixel texture
    features rather than raw luminance (see :func:`colorization.build_levin_system`
    for the intensity-based counterpart this mirrors structurally).

    Args:
        features: HxWxC texture feature array (see :func:`gabor.gabor_feature_bank`).
        win_rad: neighborhood radius (1 => 3x3 window).
        sigma: Gaussian kernel bandwidth over feature-space distance -- the
            "halting" scale: neighbors whose feature vectors differ by much
            more than ``sigma`` contribute ~0 weight (halt propagation),
            neighbors within it contribute strongly (continue propagation).

    Returns:
        A CSR sparse matrix of shape (H*W, H*W), same structure/semantics as
        :func:`colorization.build_levin_system`'s return value.
    """
    h, w = features.shape[:2]
    n = h * w
    offsets = _neighbor_offsets(win_rad)

    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    center_idx = (yy * w + xx).ravel()
    center_feat = features.reshape(n, -1)

    rows_list = []
    cols_list = []
    data_list = []

    two_sigma_sq = 2.0 * sigma * sigma

    for dy, dx in offsets:
        ny = yy + dy
        nx = xx + dx
        valid = (ny >= 0) & (ny < h) & (nx >= 0) & (nx < w)
        ny_c = np.clip(ny, 0, h - 1)
        nx_c = np.clip(nx, 0, w - 1)
        neighbor_idx = (ny_c * w + nx_c).ravel()
        neighbor_feat = features[ny_c, nx_c].reshape(n, -1)

        dist_sq = np.sum((center_feat - neighbor_feat) ** 2, axis=1)
        weight = np.exp(-dist_sq / two_sigma_sq)
        weight = np.where(valid.ravel(), weight, 0.0)

        rows_list.append(center_idx)
        cols_list.append(neighbor_idx)
        data_list.append(weight)

    rows = np.concatenate(rows_list)
    cols = np.concatenate(cols_list)
    data = np.concatenate(data_list)

    # Row-normalize so each unconstrained row's off-diagonal weights sum to
    # 1 (matching build_levin_system's normalization), then negate for the
    # (I - W) form.
    row_sum = np.zeros(n, dtype=np.float64)
    np.add.at(row_sum, rows, data)
    row_sum = np.where(row_sum < 1e-12, 1.0, row_sum)
    data_norm = -(data / row_sum[rows])

    all_rows = np.concatenate([rows, center_idx])
    all_cols = np.concatenate([cols, center_idx])
    all_data = np.concatenate([data_norm, np.ones(n)])

    return sparse.coo_matrix((all_data, (all_rows, all_cols)), shape=(n, n)).tocsr()


def colorize_scribble_screentone(
    gray: np.ndarray,
    scribble_rgb: np.ndarray,
    scribble_mask: np.ndarray,
    win_rad: int = 1,
    texture_sigma: float = 1.0,
    max_solve_dim: int = 640,
) -> np.ndarray:
    """Colorize screentoned line art from scribbles, using Gabor texture-
    feature affinity instead of intensity affinity (see module docstring).

    Same signature/return contract as
    :func:`colorization.colorize_scribble`, swap-in compatible for manga
    pages with screentone shading where the plain intensity-based solver
    would bleed color across halftone boundaries.
    """
    if gray.ndim != 2:
        raise ValueError(f"gray must be a 2-D HxW array, got shape {gray.shape}")
    if scribble_rgb.shape[:2] != gray.shape or scribble_mask.shape != gray.shape:
        raise ValueError("scribble_rgb/scribble_mask must match gray's HxW shape")
    if not np.any(scribble_mask):
        raise ValueError("scribble_mask has no scribbled pixels -- nothing to propagate from")

    # See telemetry.MANGA_COLORIZE_LOCK's docstring -- serializes the
    # OpenCV/scipy-heavy solve (this module's own Gabor filter bank plus
    # the sparse LU factorization) across independent ColorizeWorker
    # QThreads. Validation above stays outside the lock.
    from backend.src.core.telemetry import MANGA_COLORIZE_LOCK

    with MANGA_COLORIZE_LOCK:
        return _colorize_scribble_screentone_impl(
            gray, scribble_rgb, scribble_mask, win_rad, texture_sigma, max_solve_dim
        )


def _colorize_scribble_screentone_impl(
    gray: np.ndarray,
    scribble_rgb: np.ndarray,
    scribble_mask: np.ndarray,
    win_rad: int,
    texture_sigma: float,
    max_solve_dim: int,
) -> np.ndarray:
    h, w = gray.shape
    gray_u8 = gray.astype(np.uint8) if gray.dtype != np.uint8 else gray

    gray_bgr = cv2.cvtColor(gray_u8, cv2.COLOR_GRAY2BGR)
    base_ycrcb = cv2.cvtColor(gray_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float64)

    scribble_bgr = cv2.cvtColor(scribble_rgb.astype(np.uint8), cv2.COLOR_RGB2BGR)
    scribble_ycrcb_full = cv2.cvtColor(scribble_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float64)

    longest = max(h, w)
    if max_solve_dim and longest > max_solve_dim:
        scale = max_solve_dim / longest
        solve_h, solve_w = max(1, round(h * scale)), max(1, round(w * scale))

        gray_small = cv2.resize(gray_u8, (solve_w, solve_h), interpolation=cv2.INTER_AREA)
        mask_small = cv2.resize(
            scribble_mask.astype(np.uint8), (solve_w, solve_h), interpolation=cv2.INTER_NEAREST
        ).astype(bool)
        scribble_ycrcb_small = cv2.resize(
            scribble_ycrcb_full, (solve_w, solve_h), interpolation=cv2.INTER_NEAREST
        )

        if not np.any(mask_small):
            chroma = _solve_texture_chrominance(gray_u8, scribble_ycrcb_full, scribble_mask, win_rad, texture_sigma)
        else:
            chroma_small = _solve_texture_chrominance(
                gray_small, scribble_ycrcb_small, mask_small, win_rad, texture_sigma
            )
            chroma = cv2.resize(chroma_small, (w, h), interpolation=cv2.INTER_LINEAR)
    else:
        chroma = _solve_texture_chrominance(gray_u8, scribble_ycrcb_full, scribble_mask, win_rad, texture_sigma)

    out_ycrcb = base_ycrcb.copy()
    out_ycrcb[:, :, 1] = chroma[:, :, 0]
    out_ycrcb[:, :, 2] = chroma[:, :, 1]

    out_ycrcb = np.clip(out_ycrcb, 0, 255).astype(np.uint8)
    out_bgr = cv2.cvtColor(out_ycrcb, cv2.COLOR_YCrCb2BGR)
    return cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB)


def _solve_texture_chrominance(
    gray_u8: np.ndarray,
    scribble_ycrcb: np.ndarray,
    scribble_mask: np.ndarray,
    win_rad: int,
    texture_sigma: float,
) -> np.ndarray:
    h, w = gray_u8.shape
    n = h * w

    features = gabor_feature_bank(gray_u8)
    A = build_texture_affinity_system(features, win_rad=win_rad, sigma=texture_sigma).tolil()

    scribble_idx = np.nonzero(scribble_mask.ravel())[0]
    for idx in scribble_idx:
        A.rows[idx] = [idx]
        A.data[idx] = [1.0]
    lu = splu(A.tocsc())

    out = np.empty((h, w, 2), dtype=np.float64)
    for i, channel in enumerate((1, 2)):  # Cr, Cb
        b = np.zeros(n, dtype=np.float64)
        b[scribble_idx] = scribble_ycrcb[:, :, channel].ravel()[scribble_idx]
        out[:, :, i] = lu.solve(b).reshape(h, w)
    return out
