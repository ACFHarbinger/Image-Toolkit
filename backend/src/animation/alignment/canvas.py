"""
Canvas geometry, frame loading & normalization, and SCANS-mode fallback.
"""

from __future__ import annotations


from backend.src.animation.core.stateless import _largest_valid_rect

from typing import List, Tuple, Union

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
    band_px: Union[int, List[int]] = 20,
) -> np.ndarray:
    """§5.1/§5.20: Linear luminance ramp at each seam to bridge inter-strip lum gap.

    band_px may be a scalar (applied to all seams) or a list of per-seam widths.
    """
    _scalar_band = band_px if isinstance(band_px, int) else None
    if _scalar_band is not None and _scalar_band <= 0:
        return canvas
    if not seam_ys:
        return canvas
    H = canvas.shape[0]
    out = canvas.copy().astype(np.float32)

    for idx, sy in enumerate(seam_ys):
        _band = band_px[idx] if isinstance(band_px, list) else band_px
        if _band <= 0:
            continue
        ref_px = min(8, _band // 2)
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
        r0_up = max(0, sy - _band)
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
        r1_dn = min(H, sy + _band)
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


def _horizontal_fft_banding(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.21: Fraction of FFT energy at strip-boundary frequency (proxy for periodic horizontal banding).

    Computes the row-mean luminance profile (1D, length=H), removes DC, takes
    its FFT, and measures the relative energy at the spatial frequency
    corresponding to n_strips equally-spaced bands. High score = strong
    periodic banding at strip boundaries.

    Returns a score in [0, 1]. 0 = no banding at strip frequency; 1 = all
    energy concentrated at strip frequency. Returns 0.0 for degenerate input.
    """
    if img is None or n_strips < 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    H = gray.shape[0]
    if H < n_strips * 4:
        return 0.0
    # Row-mean luminance profile (length H)
    profile = gray.mean(axis=1)  # shape (H,)
    # Remove DC (mean)
    profile -= profile.mean()
    # FFT magnitude spectrum
    spectrum = np.abs(np.fft.rfft(profile))
    total_energy = float(np.sum(spectrum ** 2))
    if total_energy < 1e-6:
        return 0.0
    # Strip frequency: the banding period is strip_h = H/n_strips rows.
    # An alternating (high/low) pattern repeats every 2*strip_h rows, so the
    # dominant FFT bin is H / (2*strip_h) = n_strips // 2.
    target_bin = max(1, n_strips // 2)
    half_bw = max(1, n_strips // 4)
    lo = max(1, target_bin - half_bw)
    hi = min(len(spectrum) - 1, target_bin + half_bw)
    band_energy = float(np.sum(spectrum[lo:hi + 1] ** 2))
    return float(np.clip(band_energy / total_energy, 0.0, 1.0))


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


def _strip_luma_monotonicity(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.22: Fraction of adjacent strip pairs with luminance direction reversal (0=monotonic, 1=alternating)."""
    if img is None or n_strips < 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    H = gray.shape[0]
    strip_h = H // n_strips
    if H < n_strips or strip_h < 1:
        return 0.0
    strip_means = [float(gray[i * strip_h:(i + 1) * strip_h].mean()) for i in range(n_strips)]
    diffs = [strip_means[i + 1] - strip_means[i] for i in range(n_strips - 1)]
    if len(diffs) < 2:
        return 0.0
    reversals = sum(
        1 for i in range(len(diffs) - 1) if diffs[i] * diffs[i + 1] < 0
    )
    return float(reversals) / (len(diffs) - 1)


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


def _seam_visibility_score(img: np.ndarray) -> float:
    """§5.23: Worst-case adjacent-row luminance jump (no-reference seam visibility metric).

    Converts to grayscale, computes per-row mean, then returns max(|diff|) over
    adjacent row pairs. Black rows (mean ≤ 5) are excluded to ignore blank borders.
    """
    if img is None:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    row_means = gray.mean(axis=1)
    # exclude near-black border rows
    valid = row_means > 5.0
    valid_means = row_means[valid]
    if len(valid_means) < 2:
        return 0.0
    diffs = np.abs(np.diff(valid_means))
    return float(diffs.max())


def _chroma_seam_coherence(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.24: Mean per-channel color discontinuity at strip boundaries (chroma seam coherence).

    For each adjacent strip pair, measures the absolute difference in per-channel
    mean values. Returns the mean of all such differences across all seam boundaries
    and all channels. Higher = more visible color shift between strips.
    """
    if img is None or img.ndim != 3 or n_strips < 2:
        return 0.0
    H = img.shape[0]
    strip_h = H // n_strips
    if strip_h < 1:
        return 0.0
    strips = [img[i * strip_h:(i + 1) * strip_h] for i in range(n_strips)]
    strip_means = [s.mean(axis=(0, 1)).astype(np.float32) for s in strips]  # (3,) per strip
    diffs = []
    for i in range(len(strip_means) - 1):
        diff = float(np.abs(strip_means[i + 1] - strip_means[i]).mean())
        diffs.append(diff)
    return float(np.mean(diffs)) if diffs else 0.0


def _strip_self_ssim(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.25/§3.30: Per-strip top/bottom NCC self-consistency metric.

    Splits each of the *n_strips* horizontal bands in half and computes the
    Normalized Cross-Correlation (NCC) between the top and bottom halves.  A
    clean, spatially smooth strip should score close to 1.0; a strip that
    straddles a visible seam or has a brightness jump will score lower.

    Returns the minimum NCC across all strips.  Range [−1, 1]; values near 1.0
    indicate uniform strips.  Returns 0.0 for degenerate inputs (image too small
    or single-channel).
    """
    if img is None or img.ndim != 3 or img.shape[0] < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    H = gray.shape[0]
    strip_h = H // n_strips
    if strip_h < 2:
        return 0.0
    thumb_h = 32
    scores = []
    for i in range(n_strips):
        y0 = i * strip_h
        y1 = y0 + strip_h
        half = (y1 - y0) // 2
        if half < 1:
            continue
        top = gray[y0 : y0 + half, :]
        bot = gray[y0 + half : y1, :]
        top_t = cv2.resize(top, (top.shape[1], thumb_h), interpolation=cv2.INTER_AREA)
        bot_t = cv2.resize(bot, (bot.shape[1], thumb_h), interpolation=cv2.INTER_AREA)
        top_f = top_t.ravel() - top_t.mean()
        bot_f = bot_t.ravel() - bot_t.mean()
        denom = np.linalg.norm(top_f) * np.linalg.norm(bot_f)
        if denom < 1e-6:
            scores.append(1.0)
        else:
            scores.append(float(np.clip(np.dot(top_f, bot_f) / denom, -1.0, 1.0)))
    return min(scores) if scores else 0.0


def _strip_gradient_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.32/§3.21: Coefficient of variation of per-strip Laplacian energy.

    Splits the image into n_strips horizontal strips and computes the mean
    absolute Laplacian energy per strip.  Returns the coefficient of variation
    (std / mean) across strips.  A high CV means some strips are much sharper
    or blurrier than adjacent ones — a signature of seam-induced sharpness
    discontinuities.  Returns 0.0 for degenerate inputs.
    """
    if img is None or img.ndim != 3 or img.shape[0] < n_strips or n_strips < 2:
        return 0.0
    H = img.shape[0]
    strip_h = H // n_strips
    if strip_h < 1:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    energies = []
    for i in range(n_strips):
        y0 = i * strip_h
        y1 = y0 + strip_h
        lap = cv2.Laplacian(gray[y0:y1], cv2.CV_64F)
        energies.append(float(np.mean(np.abs(lap))))
    mean_e = float(np.mean(energies))
    if mean_e < 1e-6:
        return 0.0
    return float(np.std(energies) / mean_e)


def _seam_band_ncc_min(img: np.ndarray, n_strips: int = 8, band_px: int = 10) -> float:
    """§5.31: Minimum NCC between strip boundary bands (§3.27 in canvas).

    For each inter-strip boundary, computes the normalized cross-correlation
    between the band_px-row band immediately above and below. Returns the
    minimum NCC across all boundaries. Values near 1.0 = seamless; near 0
    or negative = visible discontinuity. Returns 1.0 for degenerate inputs.
    """
    if img is None or img.ndim != 3 or img.shape[0] < n_strips * 2 or n_strips < 2:
        return 1.0
    H = img.shape[0]
    strip_h = H // n_strips
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    min_ncc = 1.0
    for i in range(1, n_strips):
        boundary = i * strip_h
        above = gray[max(0, boundary - band_px) : boundary].ravel()
        below = gray[boundary : min(H, boundary + band_px)].ravel()
        if len(above) < 4 or len(below) < 4:
            continue
        n = min(len(above), len(below))
        a, b = above[:n], below[:n]
        a = a - a.mean()
        b = b - b.mean()
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom < 1e-6:
            continue
        ncc = float(np.dot(a, b) / denom)
        min_ncc = min(min_ncc, ncc)
    return min_ncc


def _canvas_ghosting_siqe(img: np.ndarray) -> float:
    """§5.29: FFT autocorrelation ghosting score (SIQE proxy).

    Double-image artifacts create a secondary peak in the normalized
    autocorrelation of the column-mean gradient-magnitude profile at the
    ghost displacement lag.  Score 0–100; 0=clean, 30+=likely ghost.
    """
    if img is None:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = gray.astype(np.float32)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.abs(gy)
    profile = mag.mean(axis=1)
    H = len(profile)
    if H < 20:
        return 0.0
    p = profile - profile.mean()
    n = 2 * H
    P = np.fft.rfft(p, n=n)
    acorr = np.fft.irfft(P * P.conj(), n=n)[:H]
    zero_lag = float(acorr[0])
    if zero_lag < 1e-6:
        return 0.0
    acorr /= zero_lag
    lag_min = 5
    lag_max = max(lag_min + 1, H // 4)
    secondary = float(acorr[lag_min:lag_max].max()) if lag_max > lag_min else 0.0
    return float(np.clip(secondary, 0.0, 1.0) * 100.0)


def _strip_seam_gradient_score(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.33: Max ratio of boundary-row gradient to interior-row gradient.

    Computes mean absolute luminance gradient in a ±5px window at each expected
    seam boundary row vs. the mean gradient in the strip interior. High ratio
    means hard visible seam cuts. Returns max ratio across all boundaries,
    capped at 10.0. Returns 0.0 for degenerate inputs.
    """
    if img is None or img.ndim != 3 or n_strips < 2:
        return 0.0
    H = img.shape[0]
    strip_h = H // n_strips
    if strip_h < 12:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gy = np.abs(np.diff(gray, axis=0))  # shape (H-1, W)
    band = 5
    max_ratio = 0.0
    for i in range(1, n_strips):
        boundary = i * strip_h
        b0 = max(0, boundary - band)
        b1 = min(H - 1, boundary + band)
        if b1 <= b0:
            continue
        boundary_grad = float(gy[b0:b1].mean()) if b1 > b0 else 0.0
        s0 = (i - 1) * strip_h + strip_h // 3
        s1 = i * strip_h - strip_h // 3
        if s1 > s0 and s0 < H - 1 and s1 < H:
            interior_grad = float(gy[s0:s1].mean())
        else:
            interior_grad = 0.0
        ratio = boundary_grad / (interior_grad + 1e-6)
        if ratio > max_ratio:
            max_ratio = ratio
    return float(min(max_ratio, 10.0))


def _canvas_aspect_ratio(img: np.ndarray) -> float:
    """§5.34: Height-to-width ratio of the canvas (H / W).

    A correctly stitched vertical scroll should have H >> W (portrait).
    Returns 0.0 for None input; 0.0 for zero-width images.
    """
    if img is None or img.ndim < 2:
        return 0.0
    H, W = img.shape[:2]
    return float(H) / max(float(W), 1.0)


def _strip_hist_intersection_min(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.36: Minimum histogram intersection between adjacent strips.

    Returns float in [0, 1]. 0 = completely different histograms; 1 = identical.
    Low score = color mismatch between adjacent strips (seam visible as color step).
    Returns 1.0 for degenerate inputs.
    """
    if img is None or img.ndim != 3 or img.shape[0] < n_strips * 2 or n_strips < 2:
        return 1.0
    H = img.shape[0]
    strip_h = H // n_strips
    if strip_h < 1:
        return 1.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    min_intersection = 1.0
    for i in range(n_strips - 1):
        ha = cv2.calcHist([gray[i * strip_h:(i + 1) * strip_h]], [0], None, [64], [0, 256])
        hb = cv2.calcHist([gray[(i + 1) * strip_h:(i + 2) * strip_h]], [0], None, [64], [0, 256])
        intersection = cv2.compareHist(ha, hb, cv2.HISTCMP_INTERSECT)
        sum_a = float(ha.sum())
        sum_b = float(hb.sum())
        denom = min(sum_a, sum_b)
        if denom < 1e-6:
            continue
        normalized = float(intersection / denom)
        min_intersection = min(min_intersection, normalized)
    return float(np.clip(min_intersection, 0.0, 1.0))


__all__ = [
    "_load_frames",
    "_normalise_widths",
    "_compute_canvas",
    "_crop_to_valid",
    "_telea_fill_gaps",
    "_smooth_seam_bands",
    "_correct_seam_lum_steps",
    "_canvas_gain_uniformity",
    "_horizontal_fft_banding",
    "_strip_luma_monotonicity",
    "_compute_adaptive_seam_smooth_px",
    "_per_seam_lum_step_px",
    "_scan_stitch_fallback",
    "_panorama_stitch_fallback",
    "find_optimal_sequence",
    "_detect_scroll_axis",
    "_smooth_seam_bands",
    "_compute_adaptive_seam_smooth_px",
    "_seam_coherence_score",
    "_seam_visibility_score",
    "_strip_self_ssim",
    "_chroma_seam_coherence",
    "_strip_gradient_cv",
    "_seam_band_ncc_min",
    "_canvas_ghosting_siqe",
    "_strip_seam_gradient_score",
    "_canvas_aspect_ratio",
    "_strip_hist_intersection_min",
]
