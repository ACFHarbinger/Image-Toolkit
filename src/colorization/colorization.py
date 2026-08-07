"""Levin et al. (SIGGRAPH 2004) "Colorization Using Optimization" -- quadratic-
cost scribble-based colorization, solved as a sparse linear system.

Reference: ``research/Manga Colorization and Animation Research.md`` §5.1
(``docs/moon/roadmaps/manga_colorization_animation.md`` §2.1, issue #186).

An artist provides a sparse set of colored scribbles on a grayscale line-art
image. Each unscribbled pixel's chrominance is expressed as a locally-weighted
average of its neighbors' chrominance, with weights derived from luminance
correlation (pixels of similar intensity are assumed to share color; a strong
intensity change -- e.g. a drawn line -- breaks the correlation and acts as a
natural color-boundary). This yields a large, extremely sparse linear system
(~9 nonzeros per row for a 3x3 window) that is solved once per chrominance
channel.

Deliberately a pure Python/NumPy/SciPy implementation for this first pass,
not the roadmap's originally-proposed C++ ``base::cel_shaded_generator`` Eigen kernel --
SciPy's sparse LU solver is fast enough for interactive single-page use
(a 512x512 image solves in well under a second) and this avoids opening a new
CMake/pybind11 build-system surface just to ship the first working version.
A native port remains open as a follow-up if profiling shows it's needed for
multi-page batch throughput.
"""

from __future__ import annotations

import cv2
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu

from runtime import NATIVE_COMPUTE_LOCK

__all__ = ["colorize_scribble", "build_levin_system"]

# Floor on local window variance (in normalized [0, 1] luminance units) --
# without this, a window with (near-)uniform intensity produces an
# ill-conditioned 1/variance weight blowup. Matches Levin's own reference
# implementation's use of a variance floor.
_VAR_EPS = 1e-3


def _neighbor_offsets(win_rad: int) -> np.ndarray:
    """(dy, dx) offsets for every pixel in a (2*win_rad+1)^2 window, excluding
    the center pixel itself."""
    r = np.arange(-win_rad, win_rad + 1)
    dy, dx = np.meshgrid(r, r, indexing="ij")
    offsets = np.stack([dy.ravel(), dx.ravel()], axis=1)
    center = win_rad * (2 * win_rad + 1) + win_rad
    return np.delete(offsets, center, axis=0)


def build_levin_system(y: np.ndarray, win_rad: int = 1) -> sparse.csr_matrix:
    """Build the sparse ``(I - W)`` affinity system for Levin colorization.

    Args:
        y: HxW float array, luminance normalized to [0, 1].
        win_rad: neighborhood radius (1 => 3x3 window, the paper's default).

    Returns:
        A CSR sparse matrix of shape (H*W, H*W). Row r (for an unconstrained
        pixel) sums to zero: 1 on the diagonal, ``-w_rs`` at each neighbor s,
        with the ``w_rs`` normalized to sum to 1 across r's valid neighbors.
    """
    h, w = y.shape
    n = h * w
    offsets = _neighbor_offsets(win_rad)
    win_len = offsets.shape[0]

    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    center_idx = (yy * w + xx).ravel()
    center_vals = y.ravel()

    neighbor_vals = np.empty((n, win_len), dtype=np.float64)
    neighbor_flat_idx = np.empty((n, win_len), dtype=np.int64)
    valid_mask = np.empty((n, win_len), dtype=bool)

    for k, (dy, dx) in enumerate(offsets):
        ny = yy + dy
        nx = xx + dx
        valid = (ny >= 0) & (ny < h) & (nx >= 0) & (nx < w)
        ny_c = np.clip(ny, 0, h - 1)
        nx_c = np.clip(nx, 0, w - 1)
        neighbor_vals[:, k] = y[ny_c, nx_c].ravel()
        neighbor_flat_idx[:, k] = (ny_c * w + nx_c).ravel()
        valid_mask[:, k] = valid.ravel()

    # Local window statistics (center + valid neighbors), per-pixel.
    masked_neighbors = np.where(valid_mask, neighbor_vals, np.nan)
    all_vals = np.concatenate([center_vals[:, None], masked_neighbors], axis=1)
    mu = np.nanmean(all_vals, axis=1)
    var = np.nanvar(all_vals, axis=1)
    var = np.maximum(var, _VAR_EPS)

    # Levin et al. eq. 2: w_rs ~ 1 + (1/sigma_r^2)(Y(r)-mu_r)(Y(s)-mu_r)
    w_raw = 1.0 + (1.0 / var)[:, None] * (center_vals[:, None] - mu[:, None]) * (
        neighbor_vals - mu[:, None]
    )
    w_raw = np.where(valid_mask, w_raw, 0.0)

    row_sum = w_raw.sum(axis=1, keepdims=True)
    row_sum = np.where(np.abs(row_sum) < 1e-12, 1.0, row_sum)
    w_norm = w_raw / row_sum

    rows = np.repeat(center_idx, win_len)
    cols = neighbor_flat_idx.ravel()
    data = -w_norm.ravel()

    all_rows = np.concatenate([rows, center_idx])
    all_cols = np.concatenate([cols, center_idx])
    all_data = np.concatenate([data, np.ones(n)])

    return sparse.coo_matrix((all_data, (all_rows, all_cols)), shape=(n, n)).tocsr()


def _solve_chrominance(
    y_norm: np.ndarray, scribble_ycrcb: np.ndarray, scribble_mask: np.ndarray, win_rad: int
) -> np.ndarray:
    """Solve the Levin system for a single resolution. Returns an HxWx2
    float64 array of (Cr, Cb) -- unclipped, un-typecast."""
    h, w = y_norm.shape
    n = h * w

    A = build_levin_system(y_norm, win_rad=win_rad).tolil()

    scribble_idx = np.nonzero(scribble_mask.ravel())[0]
    # Hard Dirichlet constraint: scribbled rows become identity rows so the
    # solved value there is pinned exactly to the scribble's chrominance.
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


def colorize_scribble(
    gray: np.ndarray,
    scribble_rgb: np.ndarray,
    scribble_mask: np.ndarray,
    win_rad: int = 1,
    max_solve_dim: int = 640,
) -> np.ndarray:
    """Colorize a grayscale line-art image from a sparse set of RGB scribbles.

    Args:
        gray: HxW uint8 (or float) grayscale line-art image.
        scribble_rgb: HxWx3 uint8 RGB image; only pixels where
            ``scribble_mask`` is True are read.
        scribble_mask: HxW bool array, True at every user-scribbled pixel.
        win_rad: affinity neighborhood radius (see :func:`build_levin_system`).
        max_solve_dim: if either image dimension exceeds this, the sparse
            system is solved at a downscaled resolution (longest side capped
            here) and only the two solved chrominance channels (Cr, Cb) are
            upsampled back to full resolution -- luminance (line-art detail)
            always stays at full resolution, since it is never solved for,
            only copied through. This keeps the interactive "click Colorize"
            wait time roughly constant regardless of source image size, at
            the cost of chrominance boundaries being anti-aliased at the
            downscale factor (visually minor -- chrominance is far less
            detail-sensitive than luminance for the human eye, the same
            principle chroma subsampling in JPEG/video codecs relies on).
            Pass 0 to disable and always solve at full resolution.

    Returns:
        HxWx3 uint8 RGB colorized image. The Y (luminance) channel is set
        from the input grayscale before any RGB conversion -- only
        chrominance is solved for, so line art / screentone detail is never
        blurred away by the solve itself. Note this is the YCrCb-space
        guarantee, not a pixel-exact guarantee on the final RGB output: an
        8-bit YCrCb->RGB conversion is not perfectly invertible when the
        solved chrominance would push a pixel out of the RGB gamut (the
        intermediate BGR values clip to [0, 255]), which can perturb the
        recovered Y by a few levels if you convert the RGB output back to
        YCrCb yourself. This is a property of 8-bit color-space round-
        tripping in general, not specific to this solver.
    """
    if gray.ndim != 2:
        raise ValueError(f"gray must be a 2-D HxW array, got shape {gray.shape}")
    if scribble_rgb.shape[:2] != gray.shape or scribble_mask.shape != gray.shape:
        raise ValueError("scribble_rgb/scribble_mask must match gray's HxW shape")
    if not np.any(scribble_mask):
        raise ValueError("scribble_mask has no scribbled pixels -- nothing to propagate from")

    # Serializes the OpenCV/scipy-heavy solve across independent
    # ColorizeWorker QThreads -- see telemetry.MANGA_COLORIZE_LOCK's
    # docstring for why. Validation above stays outside the lock since it's
    # cheap and independent of any shared/native state.
    with NATIVE_COMPUTE_LOCK:
        return _colorize_scribble_impl(gray, scribble_rgb, scribble_mask, win_rad, max_solve_dim)


def _colorize_scribble_impl(
    gray: np.ndarray,
    scribble_rgb: np.ndarray,
    scribble_mask: np.ndarray,
    win_rad: int,
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

        y_small = (
            cv2.resize(gray_u8, (solve_w, solve_h), interpolation=cv2.INTER_AREA).astype(np.float64)
            / 255.0
        )
        # Nearest-neighbor for the mask/scribble color so a scribble stroke
        # doesn't get diluted/erased by averaging with unscribbled neighbors.
        mask_small = cv2.resize(
            scribble_mask.astype(np.uint8), (solve_w, solve_h), interpolation=cv2.INTER_NEAREST
        ).astype(bool)
        scribble_ycrcb_small = cv2.resize(
            scribble_ycrcb_full, (solve_w, solve_h), interpolation=cv2.INTER_NEAREST
        )

        if not np.any(mask_small):
            # Degenerate case: a scribble smaller than one downsampled pixel
            # vanished under nearest-neighbor resampling -- fall back to a
            # full-resolution solve rather than raising on valid input.
            chroma = _solve_chrominance(
                gray_u8.astype(np.float64) / 255.0, scribble_ycrcb_full, scribble_mask, win_rad
            )
        else:
            chroma_small = _solve_chrominance(y_small, scribble_ycrcb_small, mask_small, win_rad)
            chroma = cv2.resize(chroma_small, (w, h), interpolation=cv2.INTER_LINEAR)
    else:
        chroma = _solve_chrominance(
            gray_u8.astype(np.float64) / 255.0, scribble_ycrcb_full, scribble_mask, win_rad
        )

    out_ycrcb = base_ycrcb.copy()
    out_ycrcb[:, :, 1] = chroma[:, :, 0]
    out_ycrcb[:, :, 2] = chroma[:, :, 1]

    out_ycrcb = np.clip(out_ycrcb, 0, 255).astype(np.uint8)
    out_bgr = cv2.cvtColor(out_ycrcb, cv2.COLOR_YCrCb2BGR)
    return cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB)
