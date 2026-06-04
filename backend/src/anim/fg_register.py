"""
backend/src/anim/fg_register.py
===============================
Foreground pose registration (Stage 8.5) — the core fix for strip-seam
character misalignment.

Problem
-------
The ASP camera model is translation-only.  It aligns the *background* across
frames perfectly, but the character is *animating* between the frames being
stitched (300–800 ms apart), so its body parts land in two different poses on
either side of every strip seam → the torn / doubled edges visible in test09.

Approach (see reports/ASP_Foreground_Assembly_Research.md §5)
------------------------------------------------------------
Both frames are first warped into the same canvas coordinate system by the
existing affines, so the *background* is already aligned.  Any optical flow
that remains on the *foreground* between the two canvas-aligned frames is the
pure animation residual ``A_animation`` (the camera component ``T_camera`` is
removed by the alignment-aware warping — it does not need to be subtracted
explicitly).

We then re-pose both frames' foreground toward the *midpoint* pose
(StabStitch++ bidirectional principle: halves the maximum per-frame
distortion).  The warp magnitude is tapered to zero away from the seam so the
correction is localised to the boundary where it matters (SC-AOF blend-band
principle) and never disturbs canvas regions a single frame owns outright.

Flow engine
-----------
Default is OpenCV ``DISOpticalFlow`` (fast, no extra dependency).  A SEA-RAFT
engine can be slotted in later via ``flow_engine="searaft"`` (requires
``ptlflow``); the rest of the module is engine-agnostic.

This module is import-safe for headless use (no Qt, no torch import at module
load) and has no side effects.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import cv2
import numpy as np

from backend.src.constants import (
    FG_REG_TAPER_PX,
    FG_REG_MAX_RESIDUAL as _FG_REG_MAX_RESIDUAL_DEFAULT,
    FG_REG_MIN_FG_PIXELS,
    FG_REG_SMOOTH_SIGMA,
)

# Allow benchmark sweeps to tune the warp-vs-single-pose threshold without an
# edit/rebuild cycle.  Lower → more seams take the single-pose fallback (one
# coherent character pose, no blend) instead of an imperfect re-pose+blend that
# can leave faint edge doubling.
try:
    FG_REG_MAX_RESIDUAL = float(
        os.environ.get("ASP_FG_MAX_RESIDUAL", _FG_REG_MAX_RESIDUAL_DEFAULT)
    )
except ValueError:
    FG_REG_MAX_RESIDUAL = _FG_REG_MAX_RESIDUAL_DEFAULT


# ---------------------------------------------------------------------------
# Flow engines  (A1: SEA-RAFT primary; DIS fallback)
# ---------------------------------------------------------------------------

_DIS_SINGLETON = None
_SEARAFT_SINGLETON = None
_SEARAFT_DEVICE = None

# SEA-RAFT is preferred when ptlflow is installed: it uses learned cost volumes
# that remain informative over flat cel-shaded regions where DIS's gradient-
# based aperture problem produces chaotic / zero flow vectors.  The model is
# loaded lazily on first call and cached for the benchmark run.
_USE_SEARAFT = os.environ.get("ASP_FLOW_ENGINE", "searaft").lower() == "searaft"

# ARAP Push phase (Sýkora 2009 block-matching Push before the Regularise step).
# Enable: ASP_ARAP_PUSH=1 (default ON).
# Disable: ASP_ARAP_PUSH=0 for A/B comparison vs pure Regularise.
_ARAP_PUSH_ENABLED = os.environ.get("ASP_ARAP_PUSH", "1") != "0"


def _get_dis():
    """Lazily construct a reusable DISOpticalFlow instance (MEDIUM preset)."""
    global _DIS_SINGLETON
    if _DIS_SINGLETON is None:
        _DIS_SINGLETON = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        try:
            _DIS_SINGLETON.setUseSpatialPropagation(True)
        except Exception:
            pass
    return _DIS_SINGLETON


def _get_searaft():
    """
    Lazily load a pretrained RAFT-class model (ptlflow required).

    Load order (first success wins):
      1. ``sea_raft`` with ``ckpt_path='things'`` — the actual SEA-RAFT pretrain.
      2. ``raft`` with ``ckpt_path='things'`` — classic RAFT, well-tested.
      3. ``raft_small`` with ``ckpt_path='things'`` — lighter fallback.

    Returns (model, device) or (None, None) when ptlflow is unavailable.
    """
    global _SEARAFT_SINGLETON, _SEARAFT_DEVICE
    if _SEARAFT_SINGLETON is not None or _SEARAFT_DEVICE == "FAILED":
        return _SEARAFT_SINGLETON, _SEARAFT_DEVICE
    try:
        import torch
        import ptlflow

        device = "cuda" if torch.cuda.is_available() else "cpu"
        loaded_name = None
        model = None
        for name, ckpt in [
            ("sea_raft", "things"),
            ("sea_raft_s", "things"),
            ("raft", "things"),
            ("raft_small", "things"),
        ]:
            try:
                model = ptlflow.get_model(name, ckpt_path=ckpt).eval().to(device)
                loaded_name = f"{name}@{ckpt}"
                break
            except Exception:
                continue
        if model is None:
            raise RuntimeError("no RAFT variant with pretrained weights found")
        _SEARAFT_SINGLETON = model
        _SEARAFT_DEVICE = device
        print(f"[FGReg] {loaded_name} loaded on {device}")
        return _SEARAFT_SINGLETON, _SEARAFT_DEVICE
    except Exception as e:
        print(f"[FGReg] RAFT (ptlflow) unavailable ({e}); using DIS fallback")
        _SEARAFT_SINGLETON = None
        _SEARAFT_DEVICE = "FAILED"
        return None, None


def _dense_flow_searaft(
    prev_bgr: np.ndarray,
    next_bgr: np.ndarray,
    fg_mask: Optional[np.ndarray] = None,
    max_side: int = 640,
) -> Optional[np.ndarray]:
    """
    Dense optical flow ``prev → next`` using RAFT (ptlflow pretrained).

    To stay within VRAM, computes flow on a downscaled version of the images
    (longest side ≤ ``max_side`` px) then upscales the flow field back.  This
    is identical to the overlap-zone-crop strategy in ``flow_refine.py``.

    Returns (H, W, 2) float32 or None if unavailable.
    """
    model, device = _get_searaft()
    if model is None:
        return None
    try:
        import torch

        H, W = prev_bgr.shape[:2]
        scale = min(1.0, max_side / max(H, W, 1))
        th, tw = max(8, int(H * scale)), max(8, int(W * scale))

        prev_s = cv2.resize(prev_bgr, (tw, th))
        next_s = cv2.resize(next_bgr, (tw, th))

        def _to_t(img: np.ndarray) -> "torch.Tensor":
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            return torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).to(device)

        with torch.no_grad():
            out = model({"images": torch.stack([_to_t(prev_s), _to_t(next_s)], dim=1)})
        # out['flows']: (1, 1, 2, th, tw) → (th, tw, 2)
        flow_s = out["flows"][0, 0].permute(1, 2, 0).cpu().numpy().astype(np.float32)

        # Scale flow vectors back to full resolution
        if scale < 1.0:
            flow_full_x = cv2.resize(flow_s[:, :, 0], (W, H)) / scale
            flow_full_y = cv2.resize(flow_s[:, :, 1], (W, H)) / scale
            flow = np.stack([flow_full_x, flow_full_y], axis=2)
        else:
            flow = flow_s
        return flow
    except Exception as e:
        print(f"[FGReg] RAFT inference failed ({e}); using DIS")
        return None


def _dense_flow(prev_bgr: np.ndarray, next_bgr: np.ndarray) -> np.ndarray:
    """
    Dense optical flow ``prev → next``.

    Uses RAFT (A1, pretrained on optical flow datasets) when available for
    robust flat-region flow; falls back to OpenCV DISOpticalFlow.

    The input is expected to be the SEAM BAND CROP (small strip around the
    seam boundary), so ``max_side=1280`` gives RAFT good resolution without
    VRAM pressure.

    Returns an (H, W, 2) float32 array ``flow`` where
    ``prev[y, x]`` corresponds to ``next[y + flow[y,x,1], x + flow[y,x,0]]``.
    """
    if _USE_SEARAFT:
        # Use 1280 max-side: seam band crops are ~440px tall × 1900px wide,
        # which downscales to ≈295×1280 — good resolution without OOM.
        flow = _dense_flow_searaft(prev_bgr, next_bgr, max_side=1280)
        if flow is not None:
            return flow
    # DIS fallback
    prev_gray = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY)
    next_gray = cv2.cvtColor(next_bgr, cv2.COLOR_BGR2GRAY)
    dis = _get_dis()
    flow = dis.calc(prev_gray, next_gray, None)
    return flow.astype(np.float32)


def _seam_taper(
    h: int,
    w: int,
    seam_pos: int,
    taper_px: float,
    axis: int = 0,
) -> np.ndarray:
    """
    (h, w) float32 taper weight, 1.0 at ``seam_pos`` decaying linearly to 0.0
    at ``±taper_px``.  ``axis=0`` → taper along rows (vertical scroll seam);
    ``axis=1`` → taper along columns (horizontal scroll seam).
    """
    if axis == 0:
        coord = np.arange(h, dtype=np.float32)[:, None]
        dist = np.abs(coord - float(seam_pos))
        w_line = np.clip(1.0 - dist / max(taper_px, 1.0), 0.0, 1.0)  # (h,1)
        return np.broadcast_to(w_line, (h, w)).copy()
    else:
        coord = np.arange(w, dtype=np.float32)[None, :]
        dist = np.abs(coord - float(seam_pos))
        w_line = np.clip(1.0 - dist / max(taper_px, 1.0), 0.0, 1.0)  # (1,w)
        return np.broadcast_to(w_line, (h, w)).copy()


def _arap_push(
    img_a: np.ndarray,
    img_b: np.ndarray,
    fg_mask: np.ndarray,
    initial_flow: np.ndarray,
    cell_size: int = 16,
    search_range: int = 24,
    min_fg_frac: float = 0.25,
    improvement_threshold: float = 0.15,
) -> np.ndarray:
    """
    ARAP Push phase (Sýkora 2009) — per-cell block matching to find better
    rigid translations before the Regularise phase smooths them.

    The Push phase decouples neighbouring cells so each can independently jump
    to its local appearance optimum via SAD (sum of absolute differences) block
    matching.  Unlike gradient-based optical flow (RAFT, DIS), block matching
    does not require local intensity gradients — it finds the best-matching
    displacement even in large flat cel-shaded regions where the aperture problem
    renders gradient methods ambiguous.

    After Push, the per-cell translations are passed to :func:`_arap_regularise`
    for global consistency (no two adjacent cells should move in wildly different
    directions).  The Push–Regularise cycle is the full Sýkora ARAP algorithm;
    the previous ASP implementation omitted the Push phase.

    Parameters
    ----------
    img_a, img_b : (H, W[, 3]) uint8
        The two canvas-aligned frame crops (seam band).
    fg_mask : (H, W) bool/uint8
        True / > 127 = foreground character pixels.  Only fg cells are pushed;
        background cells keep the initial flow.
    initial_flow : (H, W, 2) float32
        Initial per-pixel flow from the dense flow stage (RAFT/DIS).  Used both
        as the centre of the per-cell search window and as the fallback when
        block matching finds no improvement.
    cell_size : int
        Grid cell size (px).  Smaller cells = finer-grained push (more accurate)
        but slower.  Default 16 matches the ARAP regularise grid.
    search_range : int
        Half-width of the per-cell SAD search window (px).  The block matching
        looks in a (2×search_range+1)² area centred on the initial flow estimate.
    min_fg_frac : float
        Minimum fraction of a cell's pixels that must be foreground for the Push
        to run on that cell.  Background-dominated cells keep the initial flow.
    improvement_threshold : float
        Minimum fractional SAD reduction required to accept the Push displacement
        over the initial flow's displacement.  Prevents noise-driven switches.

    Returns
    -------
    (H, W, 2) float32 — updated flow with per-cell block-matched translations
    for fg cells where a clear improvement was found; otherwise identical to
    initial_flow.
    """
    H, W = initial_flow.shape[:2]
    out = initial_flow.copy()

    # Convert to grayscale for appearance-based matching
    if img_a.ndim == 3:
        gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gray_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY).astype(np.float32)
    else:
        gray_a = img_a.astype(np.float32)
        gray_b = img_b.astype(np.float32)

    fg = (fg_mask > 127) if fg_mask.dtype != bool else fg_mask
    fg_float = fg.astype(np.float32)

    n_cells_y = max(1, H // cell_size)
    n_cells_x = max(1, W // cell_size)
    min_fg_pixels = cell_size * cell_size * min_fg_frac

    for ci in range(n_cells_y):
        y0 = ci * cell_size
        y1 = min(H, y0 + cell_size)
        for cj in range(n_cells_x):
            x0 = cj * cell_size
            x1 = min(W, x0 + cell_size)

            fg_in_cell = int(fg_float[y0:y1, x0:x1].sum())
            if fg_in_cell < min_fg_pixels:
                continue  # not enough character content — keep initial flow

            # Per-cell initial flow estimate (robust median)
            cell_flow = initial_flow[y0:y1, x0:x1]
            init_dx = float(np.median(cell_flow[:, :, 0]))
            init_dy = float(np.median(cell_flow[:, :, 1]))

            # Search window in img_b centred at the initial flow estimate
            sy0 = max(0, y0 + int(round(init_dy)) - search_range)
            sy1 = min(H, y1 + int(round(init_dy)) + search_range)
            sx0 = max(0, x0 + int(round(init_dx)) - search_range)
            sx1 = min(W, x1 + int(round(init_dx)) + search_range)

            template = gray_a[y0:y1, x0:x1]
            search = gray_b[sy0:sy1, sx0:sx1]

            th, tw = template.shape
            if search.shape[0] < th or search.shape[1] < tw:
                continue  # search window too small (frame edge)

            # Compute baseline SAD at the initial flow location
            base_by = y0 + int(round(init_dy))
            base_bx = x0 + int(round(init_dx))
            if (0 <= base_by < H - th + 1) and (0 <= base_bx < W - tw + 1):
                base_patch = gray_b[base_by:base_by + th, base_bx:base_bx + tw]
                if base_patch.shape == template.shape:
                    base_sad = float(np.abs(template - base_patch).mean())
                else:
                    base_sad = float("inf")
            else:
                base_sad = float("inf")

            # SAD block matching in search window
            result = cv2.matchTemplate(
                search, template, cv2.TM_SQDIFF
            )
            _, _, min_loc, _ = cv2.minMaxLoc(result)
            best_sad = float(result[min_loc[1], min_loc[0]]) / (th * tw)

            # Accept only if Push found a genuinely better match
            if base_sad == float("inf") or best_sad < base_sad * (1.0 - improvement_threshold):
                # Convert match location back to absolute displacement
                best_dy = float(sy0 + min_loc[1]) - float(y0)
                best_dx = float(sx0 + min_loc[0]) - float(x0)
                # Update the flow in this cell (only for fg pixels)
                cell_fg = fg[y0:y1, x0:x1]
                out[y0:y1, x0:x1, 0] = np.where(cell_fg, best_dx, out[y0:y1, x0:x1, 0])
                out[y0:y1, x0:x1, 1] = np.where(cell_fg, best_dy, out[y0:y1, x0:x1, 1])

    return out


def _arap_regularise(
    flow: np.ndarray,
    fg_mask: np.ndarray,
    cell_size: int = 32,
    n_iter: int = 3,
) -> np.ndarray:
    """
    A3 — As-Rigid-As-Possible regularisation of an optical-flow field.

    Raw optical-flow vectors on anime characters can make straight line-art
    strokes "bend" during warping (each pixel moves independently, breaking
    collinearity).  ARAP regularisation fits per-cell *rigid* transformations
    (translation + rotation only, no shear/scale) to the per-pixel flow, then
    reconstructs a smooth flow by interpolating from the cell centres.  The
    result bends the character at joints rather than stretching it like fluid.

    The algorithm (Sýkora 2009, adapted for dense-flow regularisation):
      1. Divide the image into ``cell_size × cell_size`` grid cells.
      2. For each cell, compute the centroid of the fg flow vectors and a per-
         cell rotation matrix (best-fit rigid transform for the cell's vectors).
      3. Reconstruct a smooth flow from bilinear interpolation of the per-cell
         rigid centres.
      4. Iterate ``n_iter`` times (each pass makes the field smoother).

    Parameters
    ----------
    flow    : (H, W, 2) float32 — raw optical flow to regularise.
    fg_mask : (H, W) bool — True where foreground character pixels exist.
              Only fg pixels contribute to the per-cell fit; bg pixels are left
              as-is so the background plate is never perturbed.
    cell_size : Grid cell size in pixels.
    n_iter  : Number of regularise passes (1-3 is usually enough).

    Returns
    -------
    (H, W, 2) float32 — regularised flow (identical to input for bg pixels).
    """
    H, W = flow.shape[:2]
    out = flow.copy()

    for _ in range(n_iter):
        # Per-cell mean translation from fg flow vectors
        ny = max(1, H // cell_size)
        nx = max(1, W // cell_size)
        cell_tx = np.zeros((ny, nx), dtype=np.float32)
        cell_ty = np.zeros((ny, nx), dtype=np.float32)
        cell_count = np.zeros((ny, nx), dtype=np.float32)

        for ci in range(ny):
            y0, y1 = ci * cell_size, min(H, (ci + 1) * cell_size)
            for cj in range(nx):
                x0, x1 = cj * cell_size, min(W, (cj + 1) * cell_size)
                fg_cell = fg_mask[y0:y1, x0:x1]
                if fg_cell.any():
                    fx_cell = out[y0:y1, x0:x1, 0][fg_cell]
                    fy_cell = out[y0:y1, x0:x1, 1][fg_cell]
                    # Trimmed mean for outlier robustness (per-cell medoid)
                    cell_tx[ci, cj] = float(np.median(fx_cell))
                    cell_ty[ci, cj] = float(np.median(fy_cell))
                    cell_count[ci, cj] = fg_cell.sum()

        # Bilinearly interpolate per-cell rigid translations back to pixel space
        if ny > 1 and nx > 1:
            # Cell-centre coordinates
            cy_pts = np.clip(
                np.arange(ny, dtype=np.float32) * cell_size + cell_size / 2, 0, H - 1
            )
            cx_pts = np.clip(
                np.arange(nx, dtype=np.float32) * cell_size + cell_size / 2, 0, W - 1
            )
            from scipy.interpolate import RegularGridInterpolator  # lazy import
            interp_x = RegularGridInterpolator(
                (cy_pts, cx_pts), cell_tx,
                method="linear", bounds_error=False, fill_value=None,
            )
            interp_y = RegularGridInterpolator(
                (cy_pts, cx_pts), cell_ty,
                method="linear", bounds_error=False, fill_value=None,
            )
            ys, xs = np.mgrid[0:H, 0:W]
            pts = np.stack([ys.ravel(), xs.ravel()], axis=1).astype(np.float32)
            smooth_tx = interp_x(pts).reshape(H, W).astype(np.float32)
            smooth_ty = interp_y(pts).reshape(H, W).astype(np.float32)

            # Blend: fg pixels move toward the ARAP-regularised value;
            # bg pixels are left completely unchanged.
            blend = fg_mask.astype(np.float32)
            out[:, :, 0] = blend * smooth_tx + (1 - blend) * out[:, :, 0]
            out[:, :, 1] = blend * smooth_ty + (1 - blend) * out[:, :, 1]

    return out


def _remap_by_displacement(img: np.ndarray, disp: np.ndarray) -> np.ndarray:
    """
    Resample ``img`` at position ``(x + disp_x, y + disp_y)`` per pixel.

    ``disp`` is an (H, W, 2) field (dx, dy).  Pixels whose source maps outside
    the image retain their original value (BORDER_TRANSPARENT fallback) to
    avoid the BORDER_REPLICATE edge-smear artefact that creates corrupted
    corner regions in the composite when the warp shifts pixels off-canvas.
    """
    h, w = img.shape[:2]
    grid_x, grid_y = np.meshgrid(
        np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32)
    )
    map_x = grid_x + disp[:, :, 0]
    map_y = grid_y + disp[:, :, 1]
    remapped = cv2.remap(
        img,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    # Restore original pixels wherever the source coordinate mapped outside
    # the valid frame bounds — those remap to black (0) which is also content
    # in some scenes, so we use the source validity mask instead.
    out_of_bounds = (
        (map_x < 0) | (map_x >= w) | (map_y < 0) | (map_y >= h)
    )
    if out_of_bounds.any():
        out3 = np.stack([out_of_bounds] * 3, axis=2) if img.ndim == 3 else out_of_bounds
        remapped[out3] = img[out3]
    return remapped


def register_foreground_at_seam(
    warped_a: np.ndarray,
    warped_b: np.ndarray,
    fg_a: np.ndarray,
    fg_b: np.ndarray,
    seam_pos: int,
    axis: int = 0,
    taper_px: float = FG_REG_TAPER_PX,
    max_residual: float = FG_REG_MAX_RESIDUAL,
    smooth_sigma: float = FG_REG_SMOOTH_SIGMA,
    alpha_a: float = 0.5,
    alpha_b: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """
    Re-pose the foreground of two canvas-aligned frames toward a shared target
    pose in a tapered band around the seam, so character body parts line up
    across the strip boundary.

    Parameters
    ----------
    warped_a, warped_b : (H, W, 3) uint8
        The two adjacent frames already warped into canvas coordinates (so the
        background is aligned).  ``a`` owns the canvas on one side of
        ``seam_pos``; ``b`` owns the other.
    fg_a, fg_b : (H, W) bool or uint8
        Foreground masks for each warped frame (True / >127 = foreground
        character pixel).  Flow / warp is applied to foreground only.
    seam_pos : int
        Canvas row (axis=0) or column (axis=1) of the ownership boundary.
    axis : int
        0 = vertical scroll (horizontal seam), 1 = horizontal scroll.
    taper_px : float
        Half-width of the seam band over which the warp magnitude tapers to 0.
    max_residual : float
        If the median foreground residual exceeds this, the animation gap is too
        large to warp safely → return inputs unchanged and signal ``warped=False``
        so the caller can fall back to single-pose-per-component (Eden-2006).
    smooth_sigma : float
        Gaussian sigma to smooth the residual flow before warping (suppresses
        per-pixel flow noise that would tear flat cel regions).
    alpha_a, alpha_b : float in [0, 1]
        Fraction of the flow applied to frame a and b respectively.
        alpha_a + alpha_b = 1.0 (enforced).
        Default 0.5/0.5 = symmetric midpoint warp.
        Global-reference strategy sets alpha proportional to temporal distance
        from the reference strip, so strips near the reference warp less and
        distant strips warp more — preventing drift accumulation.

    Returns
    -------
    (adj_a, adj_b, info) where ``adj_a``/``adj_b`` are the re-posed frames and
    ``info`` carries diagnostics (``warped`` bool, ``residual`` median px,
    ``fg_pixels`` in the seam band).
    """
    # Normalise alphas so they sum to 1.
    total_alpha = alpha_a + alpha_b
    if total_alpha > 0:
        alpha_a = alpha_a / total_alpha
        alpha_b = alpha_b / total_alpha
    else:
        alpha_a = alpha_b = 0.5
    h, w = warped_a.shape[:2]
    fa = (fg_a > 127) if fg_a.dtype != bool else fg_a
    fb = (fg_b > 127) if fg_b.dtype != bool else fg_b

    # Seam band: only the region within taper_px of the seam matters.
    taper = _seam_taper(h, w, seam_pos, taper_px, axis=axis)  # (h,w) in [0,1]
    band = taper > 0.0
    fa_band = fa & band
    fb_band = fb & band
    fg_union = fa_band | fb_band
    n_fg = int(fg_union.sum())

    # Dominant frame in the band = the one carrying the more complete character
    # instance (more foreground pixels).  Used by the single-pose fallback (A6).
    n_a = int(fa_band.sum())
    n_b = int(fb_band.sum())
    dominant = "a" if n_a >= n_b else "b"

    info = {
        "warped": False,
        "fallback": False,
        "residual": 0.0,
        "fg_pixels": n_fg,
        "dominant": dominant,
    }

    if n_fg < FG_REG_MIN_FG_PIXELS:
        # No meaningful character content crosses this seam — nothing to fix.
        return warped_a, warped_b, info

    # Dense flow a → b (camera already removed by canvas alignment ⇒ residual
    # foreground flow is the animation motion).
    # Compute flow only on the SEAM BAND CROP (±taper_px around seam_pos) so
    # RAFT/DIS sees the relevant region at higher relative resolution instead
    # of being diluted across the full canvas (which can be 2000+ px tall).
    # This also avoids VRAM pressure from full-canvas RAFT inference.
    if axis == 0:
        y0_crop = max(0, seam_pos - int(taper_px) - 16)
        y1_crop = min(h, seam_pos + int(taper_px) + 16)
        crop_a = warped_a[y0_crop:y1_crop, :]
        crop_b = warped_b[y0_crop:y1_crop, :]
        flow_crop = _dense_flow(crop_a, crop_b)
        flow = np.zeros((h, w, 2), dtype=np.float32)
        flow[y0_crop:y1_crop, :] = flow_crop
    else:
        x0_crop = max(0, seam_pos - int(taper_px) - 16)
        x1_crop = min(w, seam_pos + int(taper_px) + 16)
        crop_a = warped_a[:, x0_crop:x1_crop]
        crop_b = warped_b[:, x0_crop:x1_crop]
        flow_crop = _dense_flow(crop_a, crop_b)
        flow = np.zeros((h, w, 2), dtype=np.float32)
        flow[:, x0_crop:x1_crop] = flow_crop

    # A3 — ARAP Push + Regularise (full Sýkora 2009 algorithm).
    #
    # Push: per-cell SAD block matching on the seam-band crops gives each cell
    # an independent appearance-optimal displacement.  Critical for flat
    # cel-shaded regions where RAFT/DIS gradient-based flow is ambiguous.
    # Regularise: smooth the per-cell translations globally so adjacent cells
    # don't move in contradictory directions (prevents line-art bending).
    # Previously only Regularise was present; Push was omitted.
    try:
        if _ARAP_PUSH_ENABLED:
            if axis == 0:
                crop_fg = fg_union[y0_crop:y1_crop, :]
                pushed = _arap_push(crop_a, crop_b, crop_fg, flow_crop,
                                    cell_size=16, search_range=24)
                flow[y0_crop:y1_crop, :] = pushed
            else:
                crop_fg = fg_union[:, x0_crop:x1_crop]
                pushed = _arap_push(crop_a, crop_b, crop_fg, flow_crop,
                                    cell_size=16, search_range=24)
                flow[:, x0_crop:x1_crop] = pushed

        flow = _arap_regularise(flow, fg_union, cell_size=16, n_iter=2)
    except Exception:
        if smooth_sigma > 0:
            flow[:, :, 0] = cv2.GaussianBlur(flow[:, :, 0], (0, 0), smooth_sigma)
            flow[:, :, 1] = cv2.GaussianBlur(flow[:, :, 1], (0, 0), smooth_sigma)

    # Magnitude of the residual on foreground pixels in the band.
    mag = np.sqrt(flow[:, :, 0] ** 2 + flow[:, :, 1] ** 2)
    fg_mag = mag[fg_union]
    med_residual = float(np.median(fg_mag)) if fg_mag.size else 0.0
    info["residual"] = round(med_residual, 2)

    if med_residual > max_residual:
        # Animation gap too large for a safe warp — signal the single-pose
        # fallback (A6): the caller should take the foreground in this seam band
        # from the dominant frame only, avoiding a two-pose double image.
        info["fallback"] = True
        return warped_a, warped_b, info

    if med_residual < 0.5:
        # Already aligned (near-static foreground at this seam) — skip.
        info["warped"] = False
        return warped_a, warped_b, info

    # Per-pixel warp weight: taper × foreground membership (warp fg only).
    w_a = (taper * fa.astype(np.float32))[:, :, None]   # (h,w,1)
    w_b = (taper * fb.astype(np.float32))[:, :, None]

    # Asymmetric re-posing toward the global reference pose.
    # flow is the vector from a→b.  In remap_by_displacement, disp is the
    # *source* offset: output[x] = input[x+disp].  So:
    #   disp_a = -alpha_a·flow  → samples frame_a content from x+alpha_a·flow,
    #                              which SHIFTS it by +alpha_a·flow (toward b).
    #   disp_b = +alpha_b·flow  → samples frame_b content from x-alpha_b·flow,
    #                              which SHIFTS it by -alpha_b·flow (toward a).
    # When alpha_a=alpha_b=0.5 this is the symmetric midpoint warp.
    # When alpha_a=1, alpha_b=0: frame a moves fully toward b (b is reference).
    disp_a = -alpha_a * flow * w_a
    disp_b = +alpha_b * flow * w_b

    # Valid-content masks: positions where the warped canvas has actual pixels.
    valid_a = warped_a.max(axis=2) > 0
    valid_b = warped_b.max(axis=2) > 0

    adj_a = _remap_by_displacement(warped_a, disp_a)
    adj_b = _remap_by_displacement(warped_b, disp_b)

    # Keep background untouched: restore original where the pixel was not warped
    # foreground (so only the character is re-posed, never the aligned bg).
    keep_a = ~(fa & band)
    keep_b = ~(fb & band)
    adj_a[keep_a] = warped_a[keep_a]
    adj_b[keep_b] = warped_b[keep_b]

    # Never introduce content where the original had none — the warp must not
    # extend canvas pixels into previously-empty boundary regions.
    adj_a[~valid_a] = 0
    adj_b[~valid_b] = 0

    # Post-warp verification: measure remaining foreground colour discrepancy
    # in a narrow strip centred on the seam.  A large post-warp diff means
    # the ARAP-regularised warp still left a significant pose mismatch that
    # will cause visible ghosting in the Laplacian blend zone.
    seam_strip_h = max(1, int(taper_px * 0.2))
    if axis == 0:
        y0_s = max(0, seam_pos - seam_strip_h)
        y1_s = min(h, seam_pos + seam_strip_h)
        strip_a = adj_a[y0_s:y1_s].astype(np.float32)
        strip_b = adj_b[y0_s:y1_s].astype(np.float32)
        fg_strip = fg_union[y0_s:y1_s]
    else:
        x0_s = max(0, seam_pos - seam_strip_h)
        x1_s = min(w, seam_pos + seam_strip_h)
        strip_a = adj_a[:, x0_s:x1_s].astype(np.float32)
        strip_b = adj_b[:, x0_s:x1_s].astype(np.float32)
        fg_strip = fg_union[:, x0_s:x1_s]

    if fg_strip.any():
        diff_fg = float(np.abs(strip_a - strip_b).mean(axis=2)[fg_strip].mean())
    else:
        diff_fg = 0.0
    info["post_warp_diff"] = round(diff_fg, 2)

    info["warped"] = True
    return adj_a, adj_b, info


__all__ = ["register_foreground_at_seam", "_dense_flow", "_seam_taper", "_arap_regularise"]
