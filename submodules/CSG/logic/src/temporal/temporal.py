"""3D (x, y, t) quadratic-cost temporal propagation (roadmap §3.1, issue #192).

Extends the Levin scribble colorizer (`colorization.py`, issue #186) so
scribbles propagate through time across an animated sequence, not just
spatially within a single frame: if an artist scribbles a character's iris
in frame 1 and frame 24, the color boundary should interpolate smoothly
through frames 2-23, not just hold each keyframe's own spatial solve in
isolation.

Per the roadmap's own recommendation, this reuses the exact same
solver -- the affinity system is built over an expanded 3D (t, y, x)
neighborhood instead of a 2D (y, x) one (same intensity-correlation
weighting, same sparse-LU solve, same Dirichlet-constraint scribble
pinning); every frame in the sequence is a solved unknown in one combined
linear system rather than being solved frame-by-frame, so color naturally
diffuses along the temporal axis through whichever frames have no scribbles
of their own. This is a direct dimensional generalization of
`colorization.py`'s `_neighbor_offsets`/`build_levin_system`, not a new
algorithm -- see that module for the full derivation and Levin et al.
(SIGGRAPH 2004) reference.

The default ``max_solve_dim`` here (128, vs. 640 for the single-frame
colorizer) is deliberately much smaller: the linear system has ``T`` times
as many unknowns as the 2D case for the same per-frame resolution, and
sparse-LU fill-in on the resulting matrix grows much faster than linearly
with the temporal window -- empirically, a 10-frame 400x400 sequence at
``max_solve_dim=256`` exhausted available memory (OOM), while the same
sequence at ``max_solve_dim=128`` solved in ~36s using ~4.4GB. This is
intended for short in-between spans at modest resolution (a handful to a
few dozen frames), the actual scope described in issue #192 -- not
full-episode timelines or full-resolution pages. A chunked/windowed solve
(overlapping temporal blocks instead of one global system) is a real,
documented follow-up if larger sequences are needed; not implemented here.
"""

from __future__ import annotations

import cv2
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu

from colorization.colorization import _VAR_EPS
from runtime import NATIVE_COMPUTE_LOCK

__all__ = ["colorize_scribble_sequence", "build_levin_system_3d"]


def _neighbor_offsets_3d(win_rad: int, t_rad: int) -> np.ndarray:
    """(dt, dy, dx) offsets for every voxel in a (2*t_rad+1)x(2*win_rad+1)^2
    window, excluding the center voxel itself."""
    rt = np.arange(-t_rad, t_rad + 1)
    r = np.arange(-win_rad, win_rad + 1)
    dt, dy, dx = np.meshgrid(rt, r, r, indexing="ij")
    offsets = np.stack([dt.ravel(), dy.ravel(), dx.ravel()], axis=1)
    return offsets[np.any(offsets != 0, axis=1)]


def build_levin_system_3d(
    y_stack: np.ndarray, win_rad: int = 1, t_rad: int = 1
) -> sparse.csr_matrix:
    """Build the sparse ``(I - W)`` affinity system for 3D (t, y, x) Levin
    colorization -- the direct temporal generalization of
    :func:`colorization.colorization.build_levin_system`.

    Args:
        y_stack: TxHxW float array, luminance normalized to [0, 1].
        win_rad: spatial neighborhood radius (1 => 3x3 window per frame).
        t_rad: temporal neighborhood radius (1 => each frame connects to
            its immediate predecessor/successor).

    Returns:
        A CSR sparse matrix of shape (T*H*W, T*H*W), same row-sums-to-zero
        structure as the 2D system.
    """
    t_dim, h, w = y_stack.shape
    n = t_dim * h * w
    offsets = _neighbor_offsets_3d(win_rad, t_rad)
    win_len = offsets.shape[0]

    tt, yy, xx = np.meshgrid(np.arange(t_dim), np.arange(h), np.arange(w), indexing="ij")
    center_idx = (tt * h * w + yy * w + xx).ravel()
    center_vals = y_stack.ravel()

    neighbor_vals = np.empty((n, win_len), dtype=np.float64)
    neighbor_flat_idx = np.empty((n, win_len), dtype=np.int64)
    valid_mask = np.empty((n, win_len), dtype=bool)

    for k, (dt, dy, dx) in enumerate(offsets):
        nt = tt + dt
        ny = yy + dy
        nx = xx + dx
        valid = (nt >= 0) & (nt < t_dim) & (ny >= 0) & (ny < h) & (nx >= 0) & (nx < w)
        nt_c = np.clip(nt, 0, t_dim - 1)
        ny_c = np.clip(ny, 0, h - 1)
        nx_c = np.clip(nx, 0, w - 1)
        neighbor_vals[:, k] = y_stack[nt_c, ny_c, nx_c].ravel()
        neighbor_flat_idx[:, k] = (nt_c * h * w + ny_c * w + nx_c).ravel()
        valid_mask[:, k] = valid.ravel()

    masked_neighbors = np.where(valid_mask, neighbor_vals, np.nan)
    all_vals = np.concatenate([center_vals[:, None], masked_neighbors], axis=1)
    mu = np.nanmean(all_vals, axis=1)
    var = np.nanvar(all_vals, axis=1)
    var = np.maximum(var, _VAR_EPS)

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


def _solve_chrominance_3d(
    y_norm_stack: np.ndarray,
    scribble_ycrcb_stack: np.ndarray,
    scribble_mask_stack: np.ndarray,
    win_rad: int,
    t_rad: int,
) -> np.ndarray:
    """Solve the 3D Levin system for a single resolution. Returns a
    TxHxWx2 float64 array of (Cr, Cb) -- unclipped, un-typecast."""
    t_dim, h, w = y_norm_stack.shape
    n = t_dim * h * w

    A = build_levin_system_3d(y_norm_stack, win_rad=win_rad, t_rad=t_rad).tolil()

    scribble_idx = np.nonzero(scribble_mask_stack.ravel())[0]
    for idx in scribble_idx:
        A.rows[idx] = [idx]
        A.data[idx] = [1.0]
    lu = splu(A.tocsc())

    flat_scribble = scribble_ycrcb_stack.reshape(n, 3)
    out = np.empty((t_dim, h, w, 2), dtype=np.float64)
    for i, channel in enumerate((1, 2)):  # Cr, Cb
        b = np.zeros(n, dtype=np.float64)
        b[scribble_idx] = flat_scribble[scribble_idx, channel]
        out[:, :, :, i] = lu.solve(b).reshape(t_dim, h, w)
    return out


def colorize_scribble_sequence(
    gray_stack: np.ndarray,
    scribble_rgb_stack: np.ndarray,
    scribble_mask_stack: np.ndarray,
    win_rad: int = 1,
    t_rad: int = 1,
    max_solve_dim: int = 128,
) -> np.ndarray:
    """Colorize a sequence of grayscale line-art frames from a sparse set of
    per-frame RGB scribbles, propagating color through both space and time.

    Typical usage: scribble only a handful of "key" frames (e.g. frame 0 and
    frame -1 of a short in-between span); every other frame's chrominance is
    solved for as part of the same combined system, so it's determined by
    whichever scribbled/solved voxels are close to it in (x, y, t) -- not
    interpolated as a separate post-process.

    Args:
        gray_stack: TxHxW uint8 (or float) grayscale line-art frames.
        scribble_rgb_stack: TxHxWx3 uint8 RGB; only pixels where
            ``scribble_mask_stack`` is True are read. Frames with no
            scribbles at all are fine -- their mask slice is all False.
        scribble_mask_stack: TxHxW bool array.
        win_rad: spatial affinity neighborhood radius (see
            :func:`build_levin_system_3d`).
        t_rad: temporal affinity neighborhood radius.
        max_solve_dim: same role as
            :func:`colorization.colorization.colorize_scribble`'s
            parameter of the same name -- caps the spatial (not temporal)
            solve resolution; chrominance is upsampled back per-frame.
            Pass 0 to disable and always solve at full resolution.

    Returns:
        TxHxWx3 uint8 RGB colorized sequence. Luminance is preserved
        exactly per-frame, same contract as :func:`colorize_scribble`.
    """
    if gray_stack.ndim != 3:
        raise ValueError(f"gray_stack must be a 3-D TxHxW array, got shape {gray_stack.shape}")
    if (
        scribble_rgb_stack.shape[:3] != gray_stack.shape
        or scribble_mask_stack.shape != gray_stack.shape
    ):
        raise ValueError(
            "scribble_rgb_stack/scribble_mask_stack must match gray_stack's TxHxW shape"
        )
    if gray_stack.shape[0] < 2:
        raise ValueError(
            "colorize_scribble_sequence needs at least 2 frames -- "
            "for a single frame use colorize_scribble"
        )
    if not np.any(scribble_mask_stack):
        raise ValueError("scribble_mask_stack has no scribbled pixels -- nothing to propagate from")

    with NATIVE_COMPUTE_LOCK:
        return _colorize_scribble_sequence_impl(
            gray_stack, scribble_rgb_stack, scribble_mask_stack, win_rad, t_rad, max_solve_dim
        )


def _colorize_scribble_sequence_impl(
    gray_stack: np.ndarray,
    scribble_rgb_stack: np.ndarray,
    scribble_mask_stack: np.ndarray,
    win_rad: int,
    t_rad: int,
    max_solve_dim: int,
) -> np.ndarray:
    t_dim, h, w = gray_stack.shape
    gray_u8 = gray_stack.astype(np.uint8) if gray_stack.dtype != np.uint8 else gray_stack

    base_ycrcb = np.empty((t_dim, h, w, 3), dtype=np.float64)
    scribble_ycrcb_full = np.empty((t_dim, h, w, 3), dtype=np.float64)
    for t in range(t_dim):
        gray_bgr = cv2.cvtColor(gray_u8[t], cv2.COLOR_GRAY2BGR)
        base_ycrcb[t] = cv2.cvtColor(gray_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float64)
        scribble_bgr = cv2.cvtColor(scribble_rgb_stack[t].astype(np.uint8), cv2.COLOR_RGB2BGR)
        scribble_ycrcb_full[t] = cv2.cvtColor(scribble_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float64)

    longest = max(h, w)
    if max_solve_dim and longest > max_solve_dim:
        scale = max_solve_dim / longest
        solve_h, solve_w = max(1, round(h * scale)), max(1, round(w * scale))

        y_small = np.empty((t_dim, solve_h, solve_w), dtype=np.float64)
        mask_small = np.empty((t_dim, solve_h, solve_w), dtype=bool)
        scribble_ycrcb_small = np.empty((t_dim, solve_h, solve_w, 3), dtype=np.float64)
        for t in range(t_dim):
            y_small[t] = (
                cv2.resize(gray_u8[t], (solve_w, solve_h), interpolation=cv2.INTER_AREA).astype(
                    np.float64
                )
                / 255.0
            )
            mask_small[t] = cv2.resize(
                scribble_mask_stack[t].astype(np.uint8),
                (solve_w, solve_h),
                interpolation=cv2.INTER_NEAREST,
            ).astype(bool)
            scribble_ycrcb_small[t] = cv2.resize(
                scribble_ycrcb_full[t], (solve_w, solve_h), interpolation=cv2.INTER_NEAREST
            )

        if not np.any(mask_small):
            # Same degenerate-downscale fallback as colorize_scribble.
            chroma = _solve_chrominance_3d(
                gray_u8.astype(np.float64) / 255.0,
                scribble_ycrcb_full,
                scribble_mask_stack,
                win_rad,
                t_rad,
            )
        else:
            chroma_small = _solve_chrominance_3d(
                y_small, scribble_ycrcb_small, mask_small, win_rad, t_rad
            )
            chroma = np.empty((t_dim, h, w, 2), dtype=np.float64)
            for t in range(t_dim):
                chroma[t] = cv2.resize(chroma_small[t], (w, h), interpolation=cv2.INTER_LINEAR)
    else:
        chroma = _solve_chrominance_3d(
            gray_u8.astype(np.float64) / 255.0,
            scribble_ycrcb_full,
            scribble_mask_stack,
            win_rad,
            t_rad,
        )

    out_ycrcb = base_ycrcb.copy()
    out_ycrcb[:, :, :, 1] = chroma[:, :, :, 0]
    out_ycrcb[:, :, :, 2] = chroma[:, :, :, 1]
    out_ycrcb = np.clip(out_ycrcb, 0, 255).astype(np.uint8)

    out_rgb = np.empty((t_dim, h, w, 3), dtype=np.uint8)
    for t in range(t_dim):
        out_bgr = cv2.cvtColor(out_ycrcb[t], cv2.COLOR_YCrCb2BGR)
        out_rgb[t] = cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB)
    return out_rgb
