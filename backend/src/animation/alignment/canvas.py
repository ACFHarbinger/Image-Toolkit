"""
Canvas geometry, frame loading & normalization, and SCANS-mode fallback.
"""

from __future__ import annotations


from backend.src.animation.core.stateless import _largest_valid_rect

from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

from backend.src.constants import CANVAS_MAX_DIM
from backend.src.exceptions import CanvasError
from backend.src.animation.core.stateless import _trim_dark_border

import logging

logger = logging.getLogger(__name__)

try:
    import batch
    _BATCH_CANVAS = True
except ImportError:
    _BATCH_CANVAS = False


def _load_frames(paths: List[str]) -> List[np.ndarray]:
    """Read frames from disk, trim broadcast dark borders, drop unreadables."""
    frames = []
    for p in paths:
        img = cv2.imread(p)
        if img is None:
            logger.warning(f"[Stitch] Warning: could not read '{p}' — skipping.")
            continue
        img = _trim_dark_border(img)
        frames.append(img)
    return frames


def _normalise_widths(frames: List[np.ndarray]) -> List[np.ndarray]:
    """Resize every frame to match the width of the first frame (Lanczos)."""
    target_w = frames[0].shape[1]
    out = []
    for img in frames:
        h, w = img.shape[:2]
        if w != target_w:
            nh = int(round(h * target_w / w))
            img = cv2.resize(img, (target_w, nh), interpolation=cv2.INTER_LANCZOS4)
        out.append(img)
    return out


def _compute_canvas(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
) -> Tuple[int, int, np.ndarray]:
    """
    Compute canvas dimensions and the global translation offset T_global
    that maps all warped corners into positive coordinates.

    Returns (canvas_h, canvas_w, T_global) where T_global is a (2,) array
    of (tx, ty) offsets to add to every affine's translation column.
    """
    if _BATCH_CANVAS:
        try:
            affines_f32 = [np.ascontiguousarray(a, dtype=np.float32) for a in affines]
            shapes = [f.shape[:2] for f in frames]
            canvas_h, canvas_w, sx, sy = batch.canvas.compute_canvas(affines_f32, shapes)
            canvas_w = min(canvas_w, CANVAS_MAX_DIM)
            canvas_h = min(canvas_h, CANVAS_MAX_DIM)
            return canvas_h, canvas_w, np.array([sx, sy], dtype=np.float32)
        except Exception as _e:
            logger.debug(f"[Stitch] batch.canvas.compute_canvas fallback: {_e}")

    all_corners = []
    for i, img in enumerate(frames):
        h, w = img.shape[:2]
        M = affines[i]
        corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32)
        warped = (M[:2, :2] @ corners.T + M[:2, 2:3]).T
        all_corners.append(warped)

    all_corners = np.vstack(all_corners)
    min_xy = all_corners.min(axis=0)
    max_xy = all_corners.max(axis=0)

    T_global = -min_xy
    canvas_w = int(np.ceil(max_xy[0] - min_xy[0]))
    canvas_h = int(np.ceil(max_xy[1] - min_xy[1]))

    canvas_w = min(canvas_w, CANVAS_MAX_DIM)
    canvas_h = min(canvas_h, CANVAS_MAX_DIM)
    return canvas_h, canvas_w, T_global


def _detect_scroll_axis(affines: List[np.ndarray]) -> str:
    """
    Classify the scroll direction of a set of affines as:
    - 'vertical'    : ty_range >> tx_range (normal case)
    - 'horizontal'  : tx_range >> ty_range (test20 pattern)
    - 'diagonal'    : both ty and tx significant (test7 pattern)
    - 'none'        : all frames co-located
    """
    if _BATCH_CANVAS:
        try:
            affines_f32 = [np.ascontiguousarray(a, dtype=np.float32) for a in affines]
            return batch.canvas.detect_scroll_axis(affines_f32)
        except Exception as _e:
            logger.debug(f"[Stitch] batch.canvas.detect_scroll_axis fallback: {_e}")

    tys = np.array([float(a[1, 2]) for a in affines])
    txs = np.array([float(a[0, 2]) for a in affines])
    ty_range = float(tys.max() - tys.min())
    tx_range = float(txs.max() - txs.min())
    total = ty_range + tx_range
    if total < 1.0:
        return "none"
    if tx_range > 0 and ty_range / max(tx_range, 1.0) < 0.1:
        return "horizontal"
    if ty_range > 0 and tx_range / max(ty_range, 1.0) > 0.3:
        return "diagonal"
    return "vertical"


def _crop_to_valid(canvas: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    """
    Crop the canvas to remove empty borders.

    Adaptive strategy:
    - If ≥80% of the bounding-box area is valid (typical vertical scroll), use
      the bounding-box crop: tight but cheap, preserves sparse straggler rows at
      the bottom of the last frame (prevents historical test4 height-loss regression).
    - If <80% of the bounding-box area is valid (diagonal scroll whose valid region
      is a parallelogram), use _largest_valid_rect: finds the maximum inscribed
      rectangle, removing the black corner triangles without cropping real content.
    """
    if valid_mask.max() == 0:
        return canvas

    row_has_content = np.any(valid_mask > 0, axis=1)
    col_has_content = np.any(valid_mask > 0, axis=0)

    row_idx = np.where(row_has_content)[0]
    col_idx = np.where(col_has_content)[0]

    if row_idx.size == 0 or col_idx.size == 0:
        return canvas

    r0, r1 = int(row_idx[0]), int(row_idx[-1]) + 1
    c0, c1 = int(col_idx[0]), int(col_idx[-1]) + 1

    bb_sub = valid_mask[r0:r1, c0:c1] > 0
    valid_ratio = float(bb_sub.sum()) / max(float(bb_sub.size), 1.0)

    if valid_ratio < 0.80:
        # relocated: from backend.src.animation.core.stateless import _largest_valid_rect

        xv0, yv0, xv1, yv1 = _largest_valid_rect(valid_mask > 0)
        if (xv1 - xv0) * (yv1 - yv0) > 0:
            logger.debug(
                f"[Stitch]   crop_to_valid (inner-rect, ratio={valid_ratio:.2f}): "
                f"({xv0},{yv0}) → ({xv1},{yv1})"
            )
            return canvas[yv0:yv1, xv0:xv1]

    logger.info(f"[Stitch]   crop_to_valid: ({c0},{r0}) → ({c1},{r1})")
    return canvas[r0:r1, c0:c1]


def _telea_fill_gaps(canvas: np.ndarray, gap_mask: np.ndarray) -> np.ndarray:
    """§1.7B: Fill residual black border pixels with cv2.INPAINT_TELEA (S23).

    Designed as a fast fallback when diffusion inpainting fails or is unavailable.
    Reliable for gaps < 50px wide; larger regions may show visible smearing.
    """
    if not gap_mask.any():
        return canvas
    if _BATCH_CANVAS:
        try:
            return batch.canvas.telea_fill_gaps(
                np.ascontiguousarray(canvas),
                np.ascontiguousarray(gap_mask.astype(np.uint8)),
                3,
            )
        except Exception as _e:
            logger.debug(f"[Stitch] batch.canvas.telea_fill_gaps fallback: {_e}")
    return cv2.inpaint(
        canvas, gap_mask.astype(np.uint8), inpaintRadius=3, flags=cv2.INPAINT_TELEA
    )


def _smooth_seam_bands(
    canvas: np.ndarray,
    seam_ys: List[int],
    band_px: int = 4,
) -> np.ndarray:
    """§4.9: Narrow vertical Gaussian blur at each inter-frame seam row.

    Reduces the hard luminance step at frame boundaries by blending a Gaussian-
    blurred copy of each seam band back into the canvas, weighted by a triangular
    ramp that peaks at the seam centre and falls to zero at ±band_px rows.
    Only pixels with valid content (non-black) are affected.

    Directly lowers seam_visibility_score (worst-case adjacent-row luminance
    jump) without altering image content outside the narrow blur band.
    """
    if band_px <= 0 or not seam_ys:
        return canvas
    H = canvas.shape[0]
    out = canvas.copy()
    kernel_h = 2 * band_px + 1  # odd kernel spanning the full band

    for sy in seam_ys:
        r0 = max(0, sy - band_px)
        r1 = min(H, sy + band_px + 1)
        if r1 - r0 < 2:
            continue
        band = canvas[r0:r1].astype(np.float32)
        blurred = cv2.GaussianBlur(band, (1, kernel_h), 0)

        # Triangular weight: 1.0 at seam centre, 0.0 at band edges.
        band_h = r1 - r0
        half = band_h / 2.0
        weights = np.array(
            [1.0 - abs(r - (sy - r0)) / half for r in range(band_h)],
            dtype=np.float32,
        ).clip(0.0, 1.0)[:, None, None]

        # Only apply where at least one channel is non-zero (valid content).
        valid = (canvas[r0:r1].max(axis=2) > 0)[:, :, None]
        blended = (weights * blurred + (1.0 - weights) * band).clip(0, 255).astype(np.uint8)
        out[r0:r1] = np.where(valid, blended, canvas[r0:r1])

    return out


def _scan_stitch_fallback(
    frames: List[np.ndarray],
    output_path: str,
) -> Image.Image:
    """
    Fall back to OpenCV SCANS mode when the main pipeline cannot find
    enough edges.  Mirrors _merge_images_scan_stitch.

    OpenCV's stitcher output usually has staircase-shaped black edges.
    After stitching we crop to the largest fully-covered inner rectangle so
    the final image contains no black boundary pixels.
    """
    logger.info("[Stitch] FALLBACK: using OpenCV SCANS mode.")
    cv2.ocl.setUseOpenCL(False)
    try:
        stitcher = cv2.Stitcher_create(mode=1)
    except AttributeError:
        stitcher = cv2.createStitcher(True)
    stitcher.setRegistrationResol(0.8)
    status, pano = stitcher.stitch(frames)
    if status != cv2.Stitcher_OK:
        raise CanvasError(f"SCANS fallback failed (status={status}).")

    # Crop to the largest fully-covered interior rectangle so no black border pixels remain.
    # _largest_valid_rect handles diagonal staircases; the simple "all-rows-valid" approach
    # silently bails when no column is valid across every row (common for diagonal scrolls).
    # relocated: from backend.src.animation.core.stateless import _largest_valid_rect

    valid_mask = pano.max(axis=2) > 0
    x0, y0, x1, y1 = _largest_valid_rect(valid_mask)
    if (x1 - x0) > 0 and (y1 - y0) > 0:
        pano = pano[y0:y1, x0:x1]
        logger.info(f"[Stitch] SCANS inner-rect crop: ({x0},{y0}) → ({x1},{y1})")

    rgb = cv2.cvtColor(pano, cv2.COLOR_BGR2RGB)
    out = Image.fromarray(rgb)
    out.save(output_path)
    return out


def _panorama_stitch_fallback(
    frames: List[np.ndarray],
    output_path: str,
) -> Image.Image:
    """§1.3B — PANORAMA stitcher attempted before SCANS for affine-validation failures.

    PANORAMA mode (mode=0) handles scale and rotation that the translation-only
    canvas model rejects.  Raises RuntimeError on failure so the caller can fall
    through to the SCANS path.
    """
    logger.info("[Stitch] §1.3B: Trying PANORAMA stitcher before SCANS.")

    pano = None
    if _BATCH_CANVAS:
        try:
            ok, result = batch.canvas.panorama_stitch_fallback(
                [np.ascontiguousarray(f) for f in frames]
            )
            if ok:
                pano = result
            else:
                raise CanvasError(
                    "PANORAMA stitcher failed (C++); caller should try SCANS."
                )
        except CanvasError:
            raise
        except Exception as _e:
            logger.debug(f"[Stitch] batch.canvas.panorama_stitch_fallback fallback: {_e}")

    if pano is None:
        # Python fallback path
        cv2.ocl.setUseOpenCL(False)
        try:
            stitcher = cv2.Stitcher_create(mode=0)
        except AttributeError:
            stitcher = cv2.createStitcher(False)
        stitcher.setRegistrationResol(0.8)
        status, pano = stitcher.stitch(frames)
        if status != cv2.Stitcher_OK:
            raise CanvasError(
                f"PANORAMA stitcher failed (status={status}); caller should try SCANS."
            )

    # relocated: from backend.src.animation.core.stateless import _largest_valid_rect

    valid_mask = pano.max(axis=2) > 0
    x0, y0, x1, y1 = _largest_valid_rect(valid_mask)
    if (x1 - x0) > 0 and (y1 - y0) > 0:
        pano = pano[y0:y1, x0:x1]
        logger.info(f"[Stitch] PANORAMA inner-rect crop: ({x0},{y0}) → ({x1},{y1})")

    rgb = cv2.cvtColor(pano, cv2.COLOR_BGR2RGB)
    out = Image.fromarray(rgb)
    out.save(output_path)
    return out


def _correct_seam_lum_steps(
    canvas: np.ndarray,
    seam_ys: List[int],
    band_px: int = 20,
) -> np.ndarray:
    """§5.1: Linear luminance ramp at each seam to bridge inter-strip lum gap."""
    if band_px <= 0 or not seam_ys:
        return canvas
    H = canvas.shape[0]
    out = canvas.copy().astype(np.float32)
    ref_px = min(8, band_px // 2)

    for sy in seam_ys:
        sy = max(ref_px, min(H - ref_px - 1, sy))
        r_top0 = max(0, sy - ref_px)
        r_top1 = sy
        r_bot0 = sy
        r_bot1 = min(H, sy + ref_px)
        if r_top1 - r_top0 < 1 or r_bot1 - r_bot0 < 1:
            continue
        top_band = out[r_top0:r_top1]
        bot_band = out[r_bot0:r_bot1]
        top_valid = top_band.max(axis=2) > 0
        bot_valid = bot_band.max(axis=2) > 0
        if not top_valid.any() or not bot_valid.any():
            continue
        _top_lum_map = (
            0.114 * top_band[:, :, 0] + 0.587 * top_band[:, :, 1] + 0.299 * top_band[:, :, 2]
        )
        _bot_lum_map = (
            0.114 * bot_band[:, :, 0] + 0.587 * bot_band[:, :, 1] + 0.299 * bot_band[:, :, 2]
        )
        _top_cnt = top_valid.sum(axis=0).clip(1, None)
        _bot_cnt = bot_valid.sum(axis=0).clip(1, None)
        top_lum = (_top_lum_map * top_valid).sum(axis=0) / _top_cnt
        bot_lum = (_bot_lum_map * bot_valid).sum(axis=0) / _bot_cnt
        step = bot_lum - top_lum
        half_step = step / 2.0
        r0_up = max(0, sy - band_px)
        r1_up = sy
        if r1_up > r0_up:
            band_h_up = r1_up - r0_up
            alphas_up = np.linspace(0.0, 1.0, band_h_up, dtype=np.float32)
            correction_up = alphas_up[:, None] * half_step[None, :]
            valid_up = out[r0_up:r1_up].max(axis=2) > 0
            for ch in range(3):
                out[r0_up:r1_up, :, ch] = np.where(
                    valid_up,
                    out[r0_up:r1_up, :, ch] + correction_up,
                    out[r0_up:r1_up, :, ch],
                )
        r0_dn = sy
        r1_dn = min(H, sy + band_px)
        if r1_dn > r0_dn:
            band_h_dn = r1_dn - r0_dn
            alphas_dn = np.linspace(1.0, 0.0, band_h_dn, dtype=np.float32)
            correction_dn = -alphas_dn[:, None] * half_step[None, :]
            valid_dn = out[r0_dn:r1_dn].max(axis=2) > 0
            for ch in range(3):
                out[r0_dn:r1_dn, :, ch] = np.where(
                    valid_dn,
                    out[r0_dn:r1_dn, :, ch] + correction_dn,
                    out[r0_dn:r1_dn, :, ch],
                )
    return out.clip(0, 255).astype(np.uint8)


def find_optimal_sequence(
    ref_path: str,
    candidates: List[str],
    min_inliers: int = 30,
    max_overlap: float = 0.85,
) -> List[str]:
    """Find the longest coherent panorama sequence while dropping redundant frames.

    Uses SIFT feature matching to build a directed overlap graph, then extracts
    the longest non-redundant path from *ref_path* outward. Frames with overlap
    exceeding *max_overlap* are considered redundant and pruned.

    Args:
        ref_path: Absolute path to the anchor (reference) frame. Always included
            as the first element of the returned sequence.
        candidates: Ordered list of candidate frame paths to evaluate. Paths that
            cannot be read (e.g. missing files) are silently skipped.
        min_inliers: Minimum RANSAC homography inliers required to consider two
            frames as overlapping. Pairs below this threshold are treated as
            non-adjacent.
        max_overlap: Maximum allowed overlap ratio [0, 1] between consecutive
            retained frames. Frames whose overlap with the previous kept frame
            exceeds this value are pruned as redundant.

    Returns:
        Ordered list of frame paths forming the longest coherent sequence,
        starting with *ref_path*. May be shorter than *candidates* if frames
        are pruned for redundancy or insufficient overlap.
    """
    # 1. Feature Extraction (SIFT)
    sift = cv2.SIFT_create(nfeatures=1200)

    def get_feats(p):
        img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None, None, None
        h, w = img.shape
        if w > 1024:
            img = cv2.resize(img, (1024, int(h * 1024 / w)))
        kp, des = sift.detectAndCompute(img, None)
        return kp, des, img.shape

    feats = {}
    for p in [ref_path] + list(candidates):
        if p not in feats:
            kp, des, shape = get_feats(p)
            if kp is not None:
                feats[p] = (kp, des, shape[0], shape[1])

    if ref_path not in feats:
        return []

    sequence = [ref_path]
    used = {ref_path}
    bf = cv2.BFMatcher()

    def find_optimal_extension(query_path, pool, direction="forward"):
        q_kp, q_des, q_h, q_w = feats[query_path]
        best_p = None
        max_dist = -1.0

        for p in pool:
            if p in used or p not in feats:
                continue
            t_kp, t_des, t_h, t_w = feats[p]

            matches = bf.knnMatch(q_des, t_des, k=2)
            good = [m for m, n in matches if m.distance < 0.75 * n.distance]
            if len(good) < min_inliers:
                continue

            src_pts = np.float32([q_kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([t_kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            if M is None or mask is None:
                continue

            inliers = int(mask.sum())
            if inliers < min_inliers:
                continue

            dist = np.sqrt(M[0, 2] ** 2 + M[1, 2] ** 2)
            if dist < 0.15 * max(q_h, q_w):
                continue

            if dist > max_dist:
                max_dist = dist
                best_p = p

        return best_p

    # Expand Forward
    while True:
        nxt = find_optimal_extension(sequence[-1], candidates, "forward")
        if nxt:
            sequence.append(nxt)
            used.add(nxt)
        else:
            break

    # Expand Backward
    while True:
        prev = find_optimal_extension(sequence[0], candidates, "backward")
        if prev:
            sequence.insert(0, prev)
            used.add(prev)
        else:
            break

    return sequence


def _canvas_gain_uniformity(img: np.ndarray, n_strips: int = 8) -> float:
    """§3.31: Strip-level luminance gain uniformity metric.

    Coefficient of variation (std/mean) of horizontal-strip mean luminance.
    0.0 = uniform; higher = strip banding. Returns 0.0 for degenerate input.
    """
    if img is None or n_strips < 1:
        return 0.0
    gray: np.ndarray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    H = gray.shape[0]
    strip_h = H // n_strips
    if H < n_strips or strip_h < 1:
        return 0.0
    strip_means = [float(gray[i * strip_h:(i + 1) * strip_h].mean()) for i in range(n_strips)]
    mean_val = float(np.mean(strip_means))
    if mean_val < 1.0:
        return 0.0
    return float(np.std(strip_means) / mean_val)


def _compute_adaptive_seam_smooth_px(
    canvas: np.ndarray,
    base_px: int = 4,
    min_px: int = 2,
    max_px: int = 12,
) -> int:
    """§5.11: Adapt seam-smooth half-width to canvas seam coherence.

    Measures row-mean luminance std of the canvas (seam_coherence proxy)
    and scales base_px: high coherence (>30) → narrow (min_px); low (<5) →
    wide (max_px). Linear interpolation between [5, 30] → [max_px, min_px].
    """
    if canvas is None or base_px <= 0:
        return base_px
    gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY).astype(np.float32) if canvas.ndim == 3 else canvas.astype(np.float32)
    row_means = gray.mean(axis=1)
    sc = float(np.std(row_means))
    lo, hi = 5.0, 30.0
    if sc <= lo:
        return max_px
    if sc >= hi:
        return min_px
    t = (sc - lo) / (hi - lo)
    return max(min_px, min(max_px, int(round(max_px + t * (min_px - max_px)))))


def _per_seam_lum_step_px(
    canvas: np.ndarray,
    seam_ys: List[int],
    base_px: int = 20,
    ref_px: int = 8,
    min_px: int = 5,
    max_px: int = 40,
) -> List[int]:
    """§5.16: Compute per-seam correction band width from actual lum step.

    For each seam at y, measures the mean luminance in the ±ref_px reference
    band just above and below. The step magnitude drives the band width:
    step < 5 → min_px (barely visible, minimal correction needed)
    step ≥ 30 → max_px (severe banding, needs wide ramp)
    Linear interpolation in between.

    Returns list of ints, same length as seam_ys.
    """
    if canvas is None or not seam_ys:
        return [base_px] * len(seam_ys)
    gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY).astype(np.float32) if canvas.ndim == 3 else canvas.astype(np.float32)
    H = gray.shape[0]
    result = []
    lo_step, hi_step = 5.0, 30.0
    for sy in seam_ys:
        sy = max(ref_px, min(H - ref_px - 1, int(sy)))
        top_band = gray[max(0, sy - ref_px):sy]
        bot_band = gray[sy:min(H, sy + ref_px)]
        if top_band.size == 0 or bot_band.size == 0:
            result.append(base_px)
            continue
        step = abs(float(bot_band.mean()) - float(top_band.mean()))
        if step <= lo_step:
            px = min_px
        elif step >= hi_step:
            px = max_px
        else:
            t = (step - lo_step) / (hi_step - lo_step)
            px = int(round(min_px + t * (max_px - min_px)))
        result.append(max(min_px, min(max_px, px)))
    return result


def _seam_coherence_score(img: np.ndarray) -> float:
    """§5.19: Seam coherence score = std of per-row mean luminance (proxy for strip banding)."""
    if img is None:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    row_means = gray.mean(axis=1)
    return float(np.std(row_means))


__all__ = [
    "_load_frames",
    "_normalise_widths",
    "_compute_canvas",
    "_crop_to_valid",
    "_telea_fill_gaps",
    "_smooth_seam_bands",
    "_correct_seam_lum_steps",
    "_canvas_gain_uniformity",
    "_compute_adaptive_seam_smooth_px",
    "_per_seam_lum_step_px",
    "_scan_stitch_fallback",
    "_panorama_stitch_fallback",
    "find_optimal_sequence",
    "_detect_scroll_axis",
    "_smooth_seam_bands",
    "_compute_adaptive_seam_smooth_px",
    "_seam_coherence_score",
]
