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


def _canvas_valid_area_ratio(img: np.ndarray, black_threshold: int = 8) -> float:
    """§5.39: Fraction of canvas pixels above the black threshold (valid content ratio).

    Converts to grayscale and returns the fraction of pixels with mean value
    > black_threshold. Low ratio = large black/empty regions = alignment failure
    or canvas significantly underfilled. Returns 1.0 for degenerate (None) input.
    """
    if img is None or img.ndim < 2:
        return 1.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    total = gray.size
    if total == 0:
        return 1.0
    valid = int(np.sum(gray > black_threshold))
    return float(valid) / float(total)


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


def _strip_sat_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.38: Coefficient of variation of per-strip mean HSV saturation."""
    if img is None or img.ndim != 3 or img.shape[0] < n_strips or n_strips < 2:
        return 0.0
    H = img.shape[0]
    strip_h = H // n_strips
    if strip_h < 1:
        return 0.0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    s = hsv[:, :, 1].astype(np.float32)
    strip_means = [float(s[i * strip_h:(i + 1) * strip_h].mean()) for i in range(n_strips)]
    mean_val = float(np.mean(strip_means))
    if mean_val < 1.0:
        return 0.0
    return float(np.std(strip_means) / mean_val)


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


def _strip_hue_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.41: Coefficient of variation of per-strip mean HSV hue (H channel).

    Computes the circular mean hue per strip using cos/sin averaging to handle
    the wrap-around at 0/180 in OpenCV's 8-bit hue representation (0–179).
    Returns the std/mean of the mean-hue angles across strips.
    Returns 0.0 for degenerate (< n_strips rows, mean saturation < 1, or n_strips < 2).
    """
    if img is None or img.ndim != 3 or img.shape[0] < n_strips or n_strips < 2:
        return 0.0
    H = img.shape[0]
    strip_h = H // n_strips
    if strip_h < 1:
        return 0.0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    s_ch = hsv[:, :, 1].astype(np.float32)
    h_ch = hsv[:, :, 0].astype(np.float32)
    mean_s = float(s_ch.mean())
    if mean_s < 1.0:
        return 0.0
    strip_hues = []
    for i in range(n_strips):
        h_strip = h_ch[i * strip_h:(i + 1) * strip_h]
        angles = h_strip * (np.pi / 90.0)
        cos_m = float(np.cos(angles).mean())
        sin_m = float(np.sin(angles).mean())
        mean_angle = float(np.arctan2(sin_m, cos_m)) % (2 * np.pi)
        strip_hues.append(mean_angle)
    mean_hue = float(np.mean(strip_hues))
    if mean_hue < 1e-6:
        return 0.0
    return float(np.std(strip_hues) / mean_hue)


def _seam_boundary_sharpness_ratio(img: np.ndarray, n_strips: int = 8, boundary_px: int = 3) -> float:
    """§5.42: Ratio of seam-boundary Laplacian variance to strip-interior variance.

    For each strip boundary row (±boundary_px around each seam), computes the
    Laplacian variance of those rows. Compares to the Laplacian variance of the
    strip interiors (middle half of each strip). Returns max ratio across boundaries.
    High ratio = seam rows are unusually sharp relative to content = hard cut.
    Returns 0.0 for degenerate inputs.
    """
    if img is None or img.ndim < 2 or img.shape[0] < n_strips * 4 or n_strips < 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    H = gray.shape[0]
    strip_h = H // n_strips
    if strip_h < 4:
        return 0.0
    lap = cv2.Laplacian(gray.astype(np.float32), cv2.CV_32F)
    max_ratio = 0.0
    for k in range(n_strips - 1):
        seam_y = (k + 1) * strip_h
        b0 = max(0, seam_y - boundary_px)
        b1 = min(H, seam_y + boundary_px)
        if b1 - b0 < 1:
            continue
        boundary_var = float(lap[b0:b1].var())
        qa = k * strip_h + strip_h // 4
        qb = k * strip_h + 3 * strip_h // 4
        qc = (k + 1) * strip_h + strip_h // 4
        qd = min(H, (k + 1) * strip_h + 3 * strip_h // 4)
        interior_a = lap[qa:qb] if qb > qa else np.array([])
        interior_b = lap[qc:qd] if qd > qc else np.array([])
        if interior_a.size == 0 and interior_b.size == 0:
            continue
        parts = [x for x in [interior_a, interior_b] if x.size > 0]
        interior_var = float(np.concatenate(parts).var())
        if interior_var < 1.0:
            continue
        ratio = boundary_var / interior_var
        if ratio > max_ratio:
            max_ratio = ratio
    return float(min(max_ratio, 50.0))


def _strip_luma_range(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.45: Absolute luminance range across horizontal strips (max − min strip mean).

    High range = strip-level luma banding from failed brightness normalization.
    Returns 0.0 for degenerate inputs (None, fewer rows than n_strips, n_strips < 2).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    strip_h = h // n_strips
    means = [float(gray[i * strip_h:(i + 1) * strip_h].mean()) for i in range(n_strips)]
    return float(max(means) - min(means))


def _seam_edge_density(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.46: Maximum Canny edge-pixel fraction across horizontal strips.

    High max density in any strip = cluttered/noisy content or hard seam artifact.
    Returns 0.0 for None or n_strips < 2.
    """
    if img is None or n_strips < 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    edges = cv2.Canny(gray, threshold1=50, threshold2=150)
    h = edges.shape[0]
    strip_h = max(1, h // n_strips)
    max_density = 0.0
    for i in range(n_strips):
        strip = edges[i * strip_h:(i + 1) * strip_h]
        if strip.size == 0:
            continue
        density = float((strip > 0).sum()) / strip.size
        if density > max_density:
            max_density = density
    return max_density


def _strip_luma_mad(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.49: Mean absolute deviation of per-strip luma means from the global mean.

    High MAD = strip-level banding where some strips are much darker/brighter
    than the average (complements luma range which only captures extremes).
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    strip_h = h // n_strips
    means = np.array([float(gray[i * strip_h:(i + 1) * strip_h].mean()) for i in range(n_strips)])
    return float(np.mean(np.abs(means - means.mean())))


def _strip_sharpness_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.50: Coefficient of variation (std/mean) of per-strip Laplacian variance.

    High CV = some strips are far sharper or blurrier than others, indicating
    composite segments from mismatched frames or failed normalization.
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips,
    mean sharpness < 1.0 guard for flat images).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    strip_h = h // n_strips
    variances = []
    for i in range(n_strips):
        strip = gray[i * strip_h:(i + 1) * strip_h]
        lap = cv2.Laplacian(strip, cv2.CV_64F)
        variances.append(float(lap.var()))
    variances = np.array(variances)
    mean_v = float(variances.mean())
    if mean_v < 1.0:
        return 0.0
    return float(variances.std() / mean_v)


def _strip_contrast_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.53: Coefficient of variation (std/mean) of per-strip luma standard deviation.

    High CV = some strips are high-contrast (sharp/noisy) while others are
    low-contrast (flat/blurry), indicating composite segments from frames with
    mismatched normalization or different scene content.
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips,
    mean per-strip std < 1.0 guard for uniformly flat images).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    strip_h = h // n_strips
    stds = np.array([float(gray[i * strip_h:(i + 1) * strip_h].std()) for i in range(n_strips)])
    mean_std = float(stds.mean())
    if mean_std < 1.0:
        return 0.0
    return float(stds.std() / mean_std)


def _seam_chroma_jump(img: np.ndarray, n_strips: int = 8, boundary_px: int = 3) -> float:
    """§5.54: Maximum per-channel mean absolute difference at strip seam boundaries.

    Measures colour discontinuities where adjacent strips meet. High value =
    colour step at the seam caused by poor inter-frame white-balance normalisation.
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips * 2,
    boundary_px < 1).
    """
    if img is None or n_strips < 2 or boundary_px < 1:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    bgr = img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    strip_h = h // n_strips
    max_jump = 0.0
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        above = bgr[max(0, boundary_row - boundary_px):boundary_row].astype(np.float32)
        below = bgr[boundary_row:min(h, boundary_row + boundary_px)].astype(np.float32)
        if above.size == 0 or below.size == 0:
            continue
        jump = float(np.abs(above.mean(axis=(0, 1)) - below.mean(axis=(0, 1))).max())
        if jump > max_jump:
            max_jump = jump
    return max_jump


def _strip_noise_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.57: Coefficient of variation (std/mean) of per-strip noise estimate.

    Noise per strip estimated as mean absolute deviation from a Gaussian-blurred
    version of the strip (blur sigma=1.5). High CV = some strips are noisy
    (high-frequency artifacts) while others are smooth, indicating composite
    segments from frames with mismatched encoding or sharpening.
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips,
    mean per-strip noise < 0.5 guard for uniformly smooth images).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    strip_h = h // n_strips
    noises = []
    for i in range(n_strips):
        strip = gray[i * strip_h:(i + 1) * strip_h].astype(np.float32)
        blurred = cv2.GaussianBlur(strip, (0, 0), 1.5)
        noises.append(float(np.abs(strip - blurred).mean()))
    noises = np.array(noises)
    mean_noise = float(noises.mean())
    if mean_noise < 0.5:
        return 0.0
    return float(noises.std() / mean_noise)


def _seam_luma_step_cv(img: np.ndarray, n_strips: int = 8, boundary_px: int = 3) -> float:
    """§5.58: Coefficient of variation (std/mean) of per-seam absolute luma step.

    Measures inconsistency in luminance discontinuities across strip boundaries.
    High CV = some seams have large luma steps while others are smooth, indicating
    unevenly-corrected gain normalization across composite zones.
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips * 2,
    boundary_px < 1, mean step < 0.5 guard for uniformly smooth seams).
    """
    if img is None or n_strips < 2 or boundary_px < 1:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    strip_h = h // n_strips
    steps = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        above = gray[max(0, boundary_row - boundary_px):boundary_row]
        below = gray[boundary_row:min(h, boundary_row + boundary_px)]
        if above.size == 0 or below.size == 0:
            continue
        steps.append(float(abs(float(above.mean()) - float(below.mean()))))
    if len(steps) < 2:
        return 0.0
    steps = np.array(steps)
    mean_step = float(steps.mean())
    if mean_step < 0.5:
        return 0.0
    return float(steps.std() / mean_step)


def _strip_entropy_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.61: Coefficient of variation (std/mean) of per-strip Shannon entropy.

    Entropy is computed from the 256-bin luma histogram (normalised to a
    probability distribution) using -sum(p*log2(p+eps)).  High CV = some
    strips carry rich information while others are flat/uniform, indicating
    composite segments from frames with very different scene complexity or
    strong background/foreground mismatch.
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips,
    mean_entropy < 0.5 guard for uniformly flat images).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    strip_h = h // n_strips
    entropies = []
    for i in range(n_strips):
        strip = gray[i * strip_h:(i + 1) * strip_h]
        hist = cv2.calcHist([strip], [0], None, [256], [0, 256]).flatten()
        hist = hist / (hist.sum() + 1e-9)
        ent = float(-np.sum(hist * np.log2(hist + 1e-9)))
        entropies.append(ent)
    entropies = np.array(entropies)
    mean_ent = float(entropies.mean())
    if mean_ent < 0.5:
        return 0.0
    return float(entropies.std() / mean_ent)


def _seam_chroma_step_cv(img: np.ndarray, n_strips: int = 8, boundary_px: int = 3) -> float:
    """§5.62: Coefficient of variation (std/mean) of per-seam absolute chroma step.

    Chroma step at each boundary = mean of |ΔCb| + |ΔCr| (YCrCb space)
    across ±boundary_px rows.  High CV = some seams have large chroma steps
    while others are colour-matched, indicating inconsistently applied
    white-balance normalisation across composite zones.
    Complements §5.60 (luma step CV) and §5.54 (seam chroma jump max).
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips*2,
    boundary_px < 1, fewer than 2 seams, mean_step < 0.5 for clean seams).
    """
    if img is None or n_strips < 2 or boundary_px < 1:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2 or img.ndim < 3:
        return 0.0
    ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb).astype(np.float32)
    cb = ycrcb[:, :, 2]
    cr = ycrcb[:, :, 1]
    strip_h = h // n_strips
    steps = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        above_cb = cb[max(0, boundary_row - boundary_px):boundary_row]
        below_cb = cb[boundary_row:min(h, boundary_row + boundary_px)]
        above_cr = cr[max(0, boundary_row - boundary_px):boundary_row]
        below_cr = cr[boundary_row:min(h, boundary_row + boundary_px)]
        if above_cb.size == 0 or below_cb.size == 0:
            continue
        delta_cb = abs(float(above_cb.mean()) - float(below_cb.mean()))
        delta_cr = abs(float(above_cr.mean()) - float(below_cr.mean()))
        steps.append(delta_cb + delta_cr)
    if len(steps) < 2:
        return 0.0
    steps = np.array(steps)
    mean_step = float(steps.mean())
    if mean_step < 0.5:
        return 0.0
    return float(steps.std() / mean_step)


def _strip_chroma_energy_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.65: Coefficient of variation (std/mean) of per-strip chroma magnitude.

    Chroma magnitude per pixel = sqrt((Cb-128)² + (Cr-128)²) in YCrCb space.
    Per-strip mean chroma magnitude; CV across strips.  High CV = some strips
    are highly saturated while others are desaturated/near-grayscale, indicating
    composite segments from frames with mismatched colour palettes.
    Orthogonal to §5.38 (HSV saturation CV) which uses a different colour model.
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips,
    grayscale input, mean chroma < 1.0 guard for near-monochrome images).
    """
    if img is None or n_strips < 2 or img.ndim < 3:
        return 0.0
    h = img.shape[0]
    if h < n_strips:
        return 0.0
    ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb).astype(np.float32)
    cb = ycrcb[:, :, 2] - 128.0
    cr = ycrcb[:, :, 1] - 128.0
    chroma_mag = np.sqrt(cb ** 2 + cr ** 2)
    strip_h = h // n_strips
    energies = []
    for i in range(n_strips):
        band = chroma_mag[i * strip_h:(i + 1) * strip_h]
        energies.append(float(band.mean()))
    energies = np.array(energies)
    mean_energy = float(energies.mean())
    if mean_energy < 1.0:
        return 0.0
    return float(energies.std() / mean_energy)


def _seam_gradient_cv(img: np.ndarray, n_strips: int = 8, band_px: int = 5) -> float:
    """§5.66: Coefficient of variation (std/mean) of per-seam vertical gradient strength.

    Gradient strength at each boundary = mean absolute row-to-row luma change
    within ±band_px rows of the boundary.  High CV = some seams are sharp
    hard cuts while others are gradual feathered transitions, indicating
    inconsistent blend width or partial seam failure.
    Orthogonal to §5.60 (luma step CV) which measures the total step size;
    this measures transition steepness regardless of step magnitude.
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips * 2,
    band_px < 2, fewer than 2 seams, mean gradient < 0.1 for flat images).
    """
    if img is None or n_strips < 2 or band_px < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    strip_h = h // n_strips
    grads = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        r0 = max(0, boundary_row - band_px)
        r1 = min(h, boundary_row + band_px)
        band = gray[r0:r1]
        if band.shape[0] < 2:
            continue
        row_diffs = np.abs(np.diff(band, axis=0))
        grads.append(float(row_diffs.mean()))
    if len(grads) < 2:
        return 0.0
    grads = np.array(grads)
    mean_grad = float(grads.mean())
    if mean_grad < 0.1:
        return 0.0
    return float(grads.std() / mean_grad)


def _strip_luma_iqr_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.69: Coefficient of variation (std/mean) of per-strip luma IQR (P75-P25).

    The inter-quartile range within each strip measures that strip's tonal
    spread over its actual pixel distribution — distinct from contrast (std),
    luma MAD (deviation of means from global), or luma range (max-min of
    means).  High CV = some strips have wide tonal ranges (complex shading)
    while others are flat solid-colour regions, indicating composite from
    frames with mismatched scene content.
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips,
    mean IQR < 1.0 guard for uniformly flat images).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    strip_h = h // n_strips
    iqrs = []
    for i in range(n_strips):
        strip = gray[i * strip_h:(i + 1) * strip_h].astype(np.float32).ravel()
        p25, p75 = float(np.percentile(strip, 25)), float(np.percentile(strip, 75))
        iqrs.append(p75 - p25)
    iqrs = np.array(iqrs)
    mean_iqr = float(iqrs.mean())
    if mean_iqr < 1.0:
        return 0.0
    return float(iqrs.std() / mean_iqr)


def _seam_column_variance_cv(img: np.ndarray, n_strips: int = 8, boundary_px: int = 3) -> float:
    """§5.70: Coefficient of variation (std/mean) of per-seam column-luma-step variance.

    At each strip boundary: compute the column-wise absolute luma step
    (difference between the mean of ±boundary_px rows above vs below,
    measured separately per column).  The variance of this per-column step
    profile is a measure of horizontal regularity at that seam — a smooth
    blend has uniform per-column steps; a partial registration failure or
    diagonal artifact has high variance.  CV of these per-seam variances
    across all seams detects when some seams are well-blended but others
    have irregular column patterns.
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips*2,
    boundary_px < 1, fewer than 2 seams, mean variance < 0.1 for flat images).
    """
    if img is None or n_strips < 2 or boundary_px < 1:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    strip_h = h // n_strips
    variances = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        above = gray[max(0, boundary_row - boundary_px):boundary_row]
        below = gray[boundary_row:min(h, boundary_row + boundary_px)]
        if above.size == 0 or below.size == 0:
            continue
        above_mean = above.mean(axis=0)
        below_mean = below.mean(axis=0)
        col_steps = np.abs(above_mean - below_mean)
        variances.append(float(col_steps.var()))
    if len(variances) < 2:
        return 0.0
    variances = np.array(variances)
    mean_var = float(variances.mean())
    if mean_var < 0.1:
        return 0.0
    return float(variances.std() / mean_var)


def _strip_luma_skewness_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.73: CV of per-strip luma skewness (|std/mean| of 3rd standardized moments).

    Positive skewness = dark strip with bright highlight tail; negative = bright strip
    with dark shadow tail. CV of absolute per-strip skewness detects inconsistent tonal
    character across strips — orthogonal to IQR-CV (§5.69, spread) and MAD-CV (§5.49).
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips*2, fewer than
    2 strips, mean_abs_skewness < 0.05 for uniform/gradient images).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    strip_h = h // n_strips
    skews = []
    for i in range(n_strips):
        strip = gray[i * strip_h:(i + 1) * strip_h].ravel()
        if strip.size < 4:
            continue
        std = strip.std()
        if std < 1.0:
            skews.append(0.0)
            continue
        skews.append(float(np.mean(((strip - strip.mean()) / std) ** 3)))
    if len(skews) < 2:
        return 0.0
    abs_skews = np.abs(np.array(skews, dtype=np.float32))
    mean_abs = float(abs_skews.mean())
    if mean_abs < 0.05:
        return 0.0
    return float(abs_skews.std() / mean_abs)


def _seam_signed_step_cv(img: np.ndarray, n_strips: int = 8, boundary_px: int = 3) -> float:
    """§5.74: CV of signed per-seam luma step (std of signed / mean of absolute).

    At each strip boundary: signed_step = mean_above − mean_below (in grayscale).
    Returns std(signed_steps) / mean(|signed_steps|). Detects alternating-direction
    normalization artifacts (bright→dark, dark→bright, bright→dark across seams) that
    §5.58 luma-step-CV misses because §5.58 uses abs() before CV. High value = seam
    steps alternate sign rather than being monotone.
    Returns 0.0 for degenerate inputs (None, n_strips < 2, boundary_px < 1,
    h < n_strips*2, fewer than 2 seams, mean_abs_step < 1.0 for flat images).
    """
    if img is None or n_strips < 2 or boundary_px < 1:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    strip_h = h // n_strips
    signed_steps = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        above = gray[max(0, boundary_row - boundary_px):boundary_row]
        below = gray[boundary_row:min(h, boundary_row + boundary_px)]
        if above.size == 0 or below.size == 0:
            continue
        signed_steps.append(float(above.mean() - below.mean()))
    if len(signed_steps) < 2:
        return 0.0
    arr = np.array(signed_steps, dtype=np.float32)
    mean_abs = float(np.abs(arr).mean())
    if mean_abs < 1.0:
        return 0.0
    return float(arr.std() / mean_abs)


def _strip_luma_kurtosis_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.77: CV of per-strip luma excess kurtosis (4th standardized moment − 3).

    High excess kurtosis = peaky or bimodal distribution (anime cel+background); low
    kurtosis = flat/uniform strip. CV of |excess kurtosis| across strips detects
    inconsistent image structure — orthogonal to §5.73 (skewness, 3rd moment) and
    §5.69 (IQR-CV, spread width).
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips*2, fewer than
    2 strips with valid std, mean_abs_kurtosis < 0.1).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    strip_h = h // n_strips
    kurts = []
    for i in range(n_strips):
        strip = gray[i * strip_h:(i + 1) * strip_h].ravel()
        if strip.size < 4:
            continue
        std = strip.std()
        if std < 1.0:
            kurts.append(0.0)
            continue
        norm = (strip - strip.mean()) / std
        kurts.append(float(np.mean(norm ** 4)) - 3.0)
    if len(kurts) < 2:
        return 0.0
    abs_kurts = np.abs(np.array(kurts, dtype=np.float32))
    mean_abs = float(abs_kurts.mean())
    if mean_abs < 0.1:
        return 0.0
    return float(abs_kurts.std() / mean_abs)


def _seam_texture_ratio_cv(img: np.ndarray, n_strips: int = 8, band_px: int = 5) -> float:
    """§5.78: CV of per-seam Laplacian-variance ratio (above / below seam band).

    At each strip boundary: computes Laplacian variance in band_px rows above and below.
    Ratio = above_var / (below_var + 1e-3). CV of log(ratio) across all seams detects
    inconsistent texture complexity matching — some seams well-matched, others crossing
    a hard texture boundary (e.g., detailed scene vs. flat sky strip).
    Orthogonal to §5.66 (seam gradient CV, step magnitude) and §5.74 (signed step CV,
    direction). Returns 0.0 for degenerate inputs (None, n_strips < 2, band_px < 1,
    h < n_strips*2, fewer than 2 seams, mean_abs(log_ratio) < 0.05).
    """
    if img is None or n_strips < 2 or band_px < 1:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    strip_h = h // n_strips
    log_ratios = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        above = gray[max(0, boundary_row - band_px):boundary_row]
        below = gray[boundary_row:min(h, boundary_row + band_px)]
        if above.shape[0] < 1 or below.shape[0] < 1:
            continue
        lap_above = cv2.Laplacian(above, cv2.CV_32F)
        lap_below = cv2.Laplacian(below, cv2.CV_32F)
        var_above = float(lap_above.var())
        var_below = float(lap_below.var())
        ratio = var_above / (var_below + 1e-3)
        if ratio < 1e-6:
            continue
        log_ratios.append(float(np.log(ratio)))
    if len(log_ratios) < 2:
        return 0.0
    arr = np.array(log_ratios, dtype=np.float32)
    mean_abs = float(np.abs(arr).mean())
    if mean_abs < 0.05:
        return 0.0
    return float(arr.std() / (mean_abs + 1e-9))


def _strip_edge_density_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.81: CV of per-strip Canny edge pixel fraction.

    Each strip's edge density = fraction of pixels flagged by Canny(50,150).
    CV of densities across strips detects inconsistent detail level — some
    strips with dense edge maps (complex scene) and others flat (sky/wall).
    Orthogonal to §5.50 (sharpness-CV uses Laplacian std, not edge count)
    and §5.46 (seam edge density is a single value at seam boundaries).
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips*2,
    fewer than 2 strips, mean_density < 0.005 for nearly-blank images).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)
    strip_h = h // n_strips
    densities = []
    for i in range(n_strips):
        strip = gray[i * strip_h:(i + 1) * strip_h]
        if strip.size == 0:
            continue
        edges = cv2.Canny(strip, 50, 150)
        densities.append(float(edges.mean()) / 255.0)
    if len(densities) < 2:
        return 0.0
    densities = np.array(densities, dtype=np.float32)
    mean_d = float(densities.mean())
    if mean_d < 0.005:
        return 0.0
    return float(densities.std() / mean_d)


def _seam_local_contrast_cv(img: np.ndarray, n_strips: int = 8, band_px: int = 5) -> float:
    """§5.82: CV of per-seam local luma contrast (pixel std in ±band_px seam band).

    At each strip boundary: std of all grayscale pixels in the ±band_px band
    around the seam. High std = high-contrast region (detail); low std = flat
    region (sky, wall). CV across seams detects inconsistent local complexity —
    some seams are in rich-texture areas while others are in flat zones.
    Orthogonal to §5.78 (texture ratio compares above vs. below) and §5.66
    (gradient CV measures step steepness, not absolute contrast level).
    Returns 0.0 for degenerate inputs (None, n_strips < 2, band_px < 1,
    h < n_strips*2, fewer than 2 seams, mean_contrast < 1.0).
    """
    if img is None or n_strips < 2 or band_px < 1:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    strip_h = h // n_strips
    contrasts = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        band = gray[max(0, boundary_row - band_px):min(h, boundary_row + band_px)]
        if band.size == 0:
            continue
        contrasts.append(float(band.std()))
    if len(contrasts) < 2:
        return 0.0
    contrasts = np.array(contrasts, dtype=np.float32)
    mean_c = float(contrasts.mean())
    if mean_c < 1.0:
        return 0.0
    return float(contrasts.std() / mean_c)


def _strip_sobel_energy_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.93: CV of per-strip mean Sobel gradient energy (mean |∇|).

    Each strip's Sobel energy = mean of sqrt(Gx²+Gy²) across all pixels.
    CV across strips detects inconsistent directional gradient activity —
    orthogonal to §5.50 (Laplacian std/mean, different operator/normalisation),
    §5.81 (Canny binary edge density), and §5.66 (seam boundary step only).
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips*2,
    fewer than 2 strips, mean_energy < 0.5 for nearly-blank images).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    strip_h = h // n_strips
    energies = []
    for i in range(n_strips):
        strip = gray[i * strip_h:(i + 1) * strip_h]
        if strip.size == 0:
            continue
        gx = cv2.Sobel(strip, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(strip, cv2.CV_32F, 0, 1, ksize=3)
        energies.append(float(np.sqrt(gx ** 2 + gy ** 2).mean()))
    if len(energies) < 2:
        return 0.0
    energies = np.array(energies, dtype=np.float32)
    mean_e = float(energies.mean())
    if mean_e < 0.5:
        return 0.0
    return float(energies.std() / mean_e)


def _seam_value_shift_cv(img: np.ndarray, n_strips: int = 8, boundary_px: int = 3) -> float:
    """§5.94: CV of per-seam absolute HSV Value shift (|V_above − V_below|).

    HSV Value = max(R,G,B).  Detects cross-seam brightness mismatches that
    luma (weighted mean of channels) can miss when the dominant channel differs.
    Orthogonal to §5.86 (hue shift), §5.90 (saturation shift), and §5.58/§5.60
    (luma = 0.114B+0.587G+0.299R, different from max-channel brightness).
    Returns 0.0 for grayscale, fewer than 2 seams, or mean_shift < 1.0.
    """
    if img is None or n_strips < 2 or boundary_px < 1:
        return 0.0
    if img.ndim != 3 or img.shape[2] != 3:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    val = hsv[:, :, 2]  # [0, 255]
    strip_h = h // n_strips
    shifts = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        above = val[max(0, boundary_row - boundary_px):boundary_row]
        below = val[boundary_row:min(h, boundary_row + boundary_px)]
        if above.size == 0 or below.size == 0:
            continue
        shifts.append(abs(float(above.mean()) - float(below.mean())))
    if len(shifts) < 2:
        return 0.0
    shifts = np.array(shifts, dtype=np.float32)
    mean_s = float(shifts.mean())
    if mean_s < 1.0:
        return 0.0
    return float(shifts.std() / mean_s)


def _strip_median_luma_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.97: CV of per-strip median luma (P50).

    Median is the typical brightness of each strip — robust to outliers.
    CV of medians across strips detects strips with different typical
    brightnesses, orthogonal to spread metrics (§5.85 P90−P10, §5.69 IQR,
    §5.49 MAD) which measure width, not central location.
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips*2,
    fewer than 2 strips, mean_median < 1.0 for nearly-black images).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    strip_h = h // n_strips
    medians = []
    for i in range(n_strips):
        strip = gray[i * strip_h:(i + 1) * strip_h].ravel()
        if strip.size == 0:
            continue
        medians.append(float(np.median(strip)))
    if len(medians) < 2:
        return 0.0
    medians = np.array(medians, dtype=np.float32)
    mean_m = float(medians.mean())
    if mean_m < 1.0:
        return 0.0
    return float(medians.std() / mean_m)


def _seam_entropy_shift_cv(img: np.ndarray, n_strips: int = 8, boundary_px: int = 3) -> float:
    """§5.98: CV of per-seam absolute Shannon entropy shift (|H_above − H_below|).

    At each strip boundary: Shannon entropy of pixel histogram (256 bins,
    base-2) for ±boundary_px rows above and below.  Absolute difference
    detects information-content mismatch at each seam.  CV across seams
    flags inconsistent content complexity matching.
    Orthogonal to §5.61 (strip entropy CV, cross-strip not cross-seam),
    §5.82 (seam local contrast, pixel std not entropy), §5.78 (Laplacian
    variance ratio, not histogram entropy).
    Returns 0.0 for degenerate inputs (None, n_strips < 2, boundary_px < 1,
    h < n_strips*2, fewer than 2 seams, mean_shift < 0.05).
    """
    if img is None or n_strips < 2 or boundary_px < 1:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)
    strip_h = h // n_strips

    def _entropy(band: np.ndarray) -> float:
        hist = np.bincount(band.ravel(), minlength=256).astype(np.float32)
        hist = hist[hist > 0]
        p = hist / hist.sum()
        return float(-np.sum(p * np.log2(p)))

    shifts = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        above = gray[max(0, boundary_row - boundary_px):boundary_row]
        below = gray[boundary_row:min(h, boundary_row + boundary_px)]
        if above.size == 0 or below.size == 0:
            continue
        shifts.append(abs(_entropy(above) - _entropy(below)))
    if len(shifts) < 2:
        return 0.0
    shifts = np.array(shifts, dtype=np.float32)
    mean_s = float(shifts.mean())
    if mean_s < 0.05:
        return 0.0
    return float(shifts.std() / mean_s)


def _strip_red_channel_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.101: CV of per-strip mean Red channel value.

    Each strip's mean R value (BGR channel 2).  CV across strips detects
    inconsistent red-channel content — orthogonal to luma (weighted sum),
    §5.94 Value (max channel), §5.86 hue angle, and §5.90 saturation shift.
    Returns 0.0 for grayscale input, fewer than 2 strips, or mean_red < 1.0.
    """
    if img is None or n_strips < 2:
        return 0.0
    if img.ndim != 3 or img.shape[2] != 3:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    red = img[:, :, 2].astype(np.float32)  # BGR: channel 2 = Red
    strip_h = h // n_strips
    means = []
    for i in range(n_strips):
        strip = red[i * strip_h:(i + 1) * strip_h]
        if strip.size == 0:
            continue
        means.append(float(strip.mean()))
    if len(means) < 2:
        return 0.0
    means = np.array(means, dtype=np.float32)
    mean_r = float(means.mean())
    if mean_r < 1.0:
        return 0.0
    return float(means.std() / mean_r)


def _seam_blue_shift_cv(img: np.ndarray, n_strips: int = 8, boundary_px: int = 3) -> float:
    """§5.102: CV of per-seam absolute Blue channel shift (|B_above − B_below|).

    At each strip boundary: absolute difference of mean Blue (BGR channel 0)
    in ±boundary_px rows.  Detects inconsistent blue-axis normalization at
    seams — orthogonal to luma step (§5.58 weighted average), Value shift
    (§5.94 max channel), hue angle (§5.86), and saturation shift (§5.90).
    Returns 0.0 for grayscale, fewer than 2 seams, or mean_shift < 1.0.
    """
    if img is None or n_strips < 2 or boundary_px < 1:
        return 0.0
    if img.ndim != 3 or img.shape[2] != 3:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    blue = img[:, :, 0].astype(np.float32)  # BGR: channel 0 = Blue
    strip_h = h // n_strips
    shifts = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        above = blue[max(0, boundary_row - boundary_px):boundary_row]
        below = blue[boundary_row:min(h, boundary_row + boundary_px)]
        if above.size == 0 or below.size == 0:
            continue
        shifts.append(abs(float(above.mean()) - float(below.mean())))
    if len(shifts) < 2:
        return 0.0
    shifts = np.array(shifts, dtype=np.float32)
    mean_s = float(shifts.mean())
    if mean_s < 1.0:
        return 0.0
    return float(shifts.std() / mean_s)


def _strip_green_channel_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.105: CV of per-strip mean Green channel value."""
    if img is None or n_strips < 2:
        return 0.0
    if img.ndim != 3 or img.shape[2] != 3:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    green = img[:, :, 1].astype(np.float32)  # BGR: channel 1 = Green
    strip_h = h // n_strips
    means = []
    for i in range(n_strips):
        strip = green[i * strip_h:(i + 1) * strip_h]
        if strip.size == 0:
            continue
        means.append(float(strip.mean()))
    if len(means) < 2:
        return 0.0
    means = np.array(means, dtype=np.float32)
    mean_g = float(means.mean())
    if mean_g < 1.0:
        return 0.0
    return float(means.std() / mean_g)


def _seam_red_shift_cv(img: np.ndarray, n_strips: int = 8, boundary_px: int = 3) -> float:
    """§5.106: CV of per-seam absolute Red channel shift (|R_above − R_below|)."""
    if img is None or n_strips < 2 or boundary_px < 1:
        return 0.0
    if img.ndim != 3 or img.shape[2] != 3:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    red = img[:, :, 2].astype(np.float32)  # BGR: channel 2 = Red
    strip_h = h // n_strips
    shifts = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        above = red[max(0, boundary_row - boundary_px):boundary_row]
        below = red[boundary_row:min(h, boundary_row + boundary_px)]
        if above.size == 0 or below.size == 0:
            continue
        shifts.append(abs(float(above.mean()) - float(below.mean())))
    if len(shifts) < 2:
        return 0.0
    shifts = np.array(shifts, dtype=np.float32)
    mean_s = float(shifts.mean())
    if mean_s < 1.0:
        return 0.0
    return float(shifts.std() / mean_s)


def _strip_blue_channel_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.109: CV of per-strip mean Blue channel value."""
    if img is None or n_strips < 2:
        return 0.0
    if img.ndim != 3 or img.shape[2] != 3:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    blue = img[:, :, 0].astype(np.float32)  # BGR: channel 0 = Blue
    strip_h = h // n_strips
    means = []
    for i in range(n_strips):
        strip = blue[i * strip_h:(i + 1) * strip_h]
        if strip.size == 0:
            continue
        means.append(float(strip.mean()))
    if len(means) < 2:
        return 0.0
    means = np.array(means, dtype=np.float32)
    mean_b = float(means.mean())
    if mean_b < 1.0:
        return 0.0
    return float(means.std() / mean_b)


def _seam_green_shift_cv(img: np.ndarray, n_strips: int = 8, boundary_px: int = 3) -> float:
    """§5.110: CV of per-seam absolute Green channel shift (|G_above − G_below|)."""
    if img is None or n_strips < 2 or boundary_px < 1:
        return 0.0
    if img.ndim != 3 or img.shape[2] != 3:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    green = img[:, :, 1].astype(np.float32)  # BGR: channel 1 = Green
    strip_h = h // n_strips
    shifts = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        above = green[max(0, boundary_row - boundary_px):boundary_row]
        below = green[boundary_row:min(h, boundary_row + boundary_px)]
        if above.size == 0 or below.size == 0:
            continue
        shifts.append(abs(float(above.mean()) - float(below.mean())))
    if len(shifts) < 2:
        return 0.0
    shifts = np.array(shifts, dtype=np.float32)
    mean_s = float(shifts.mean())
    if mean_s < 1.0:
        return 0.0
    return float(shifts.std() / mean_s)


__all__ = [
    "_load_frames",
    "_normalise_widths",
    "_compute_canvas",
    "_crop_to_valid",
    "_strip_noise_cv",
    "_telea_fill_gaps",
    "_canvas_valid_area_ratio",
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
    "_strip_sat_cv",
    "_canvas_valid_area_ratio",
    "_seam_boundary_sharpness_ratio",
    "_strip_hue_cv",
    "_strip_luma_range",
    "_seam_edge_density",
    "_strip_luma_mad",
    "_strip_sharpness_cv",
    "_strip_contrast_cv",
    "_seam_chroma_jump",
    "_seam_luma_step_cv",
    "_strip_entropy_cv",
    "_seam_chroma_step_cv",
    "_strip_chroma_energy_cv",
    "_seam_gradient_cv",
    "_strip_luma_iqr_cv",
    "_seam_column_variance_cv",
    "_strip_luma_skewness_cv",
    "_seam_signed_step_cv",
    "_strip_luma_kurtosis_cv",
    "_seam_texture_ratio_cv",
    "_strip_edge_density_cv",
    "_seam_local_contrast_cv",
    "_strip_luma_p90p10_cv",
    "_seam_hue_shift_cv",
    "_strip_dark_pixel_fraction_cv",
    "_seam_saturation_shift_cv",
    "_strip_sobel_energy_cv",
    "_seam_value_shift_cv",
    "_strip_median_luma_cv",
    "_seam_entropy_shift_cv",
    "_strip_red_channel_cv",
    "_seam_blue_shift_cv",
    "_strip_green_channel_cv",
    "_seam_red_shift_cv",
    "_strip_blue_channel_cv",
    "_seam_green_shift_cv",
]


def _strip_luma_p90p10_cv(img: np.ndarray, n_strips: int = 8) -> float:
    """§5.85: CV of per-strip luma P90–P10 percentile spread.

    P90−P10 is a robust tonal range (excludes top/bottom 10% outliers).
    Orthogonal to §5.45 (full range = max−min), §5.69 (IQR = P75−P25, narrower),
    and §5.49 (MAD = median-centred deviation).  CV across strips detects
    strips with very different outlier-robust tonal extents.
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips*2,
    fewer than 2 strips, mean_spread < 1.0 for nearly-flat images).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
    strip_h = h // n_strips
    spreads = []
    for i in range(n_strips):
        strip = gray[i * strip_h:(i + 1) * strip_h].ravel()
        if strip.size < 4:
            continue
        p10, p90 = float(np.percentile(strip, 10)), float(np.percentile(strip, 90))
        spreads.append(p90 - p10)
    if len(spreads) < 2:
        return 0.0
    spreads = np.array(spreads, dtype=np.float32)
    mean_s = float(spreads.mean())
    if mean_s < 1.0:
        return 0.0
    return float(spreads.std() / mean_s)


def _seam_hue_shift_cv(img: np.ndarray, n_strips: int = 8, boundary_px: int = 3) -> float:
    """§5.86: CV of per-seam absolute mean hue shift (degrees, [0,180]).

    At each strip boundary: mean hue of ±boundary_px rows above minus mean hue
    below (converted to [0,180] for circular robustness).  CV of these absolute
    hue differences detects inconsistent cross-seam colour matching.
    Orthogonal to §5.62 (YCrCb chroma step magnitude), §5.54 (max chroma jump),
    and §5.41 (within-strip hue spread).
    Returns 0.0 for grayscale input, fewer than 2 seams, or mean_shift < 1.0.
    """
    if img is None or n_strips < 2 or boundary_px < 1:
        return 0.0
    if img.ndim != 3 or img.shape[2] != 3:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    hue = hsv[:, :, 0]  # OpenCV: hue in [0, 180)
    strip_h = h // n_strips
    shifts = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        above = hue[max(0, boundary_row - boundary_px):boundary_row]
        below = hue[boundary_row:min(h, boundary_row + boundary_px)]
        if above.size == 0 or below.size == 0:
            continue
        diff = float(above.mean()) - float(below.mean())
        # Wrap to [−90, 90] then take abs → [0, 90]
        diff = ((diff + 90.0) % 180.0) - 90.0
        shifts.append(abs(diff))
    if len(shifts) < 2:
        return 0.0
    shifts = np.array(shifts, dtype=np.float32)
    mean_s = float(shifts.mean())
    if mean_s < 1.0:
        return 0.0
    return float(shifts.std() / mean_s)


def _strip_dark_pixel_fraction_cv(img: np.ndarray, n_strips: int = 8, threshold: int = 64) -> float:
    """§5.89: CV of per-strip dark pixel fraction (luma < threshold).

    Each strip's dark fraction = count(pixels < threshold) / total_pixels.
    CV across strips detects tonal inconsistency where some strips are mostly
    bright and others mostly dark — orthogonal to §5.85 (P90−P10 spread),
    §5.73 (skewness, asymmetry), and §5.45 (full luma range).
    Returns 0.0 for degenerate inputs (None, n_strips < 2, h < n_strips*2,
    fewer than 2 strips, mean_fraction < 0.005 or mean_fraction > 0.995).
    """
    if img is None or n_strips < 2:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
    gray = gray.astype(np.float32)
    strip_h = h // n_strips
    fractions = []
    for i in range(n_strips):
        strip = gray[i * strip_h:(i + 1) * strip_h].ravel()
        if strip.size == 0:
            continue
        fractions.append(float((strip < threshold).sum()) / strip.size)
    if len(fractions) < 2:
        return 0.0
    fractions = np.array(fractions, dtype=np.float32)
    mean_f = float(fractions.mean())
    if mean_f < 0.005 or mean_f > 0.995:
        return 0.0
    return float(fractions.std() / mean_f)


def _seam_saturation_shift_cv(img: np.ndarray, n_strips: int = 8, boundary_px: int = 3) -> float:
    """§5.90: CV of per-seam absolute mean HSV saturation shift.

    At each strip boundary: |mean_saturation_above − mean_saturation_below|
    (HSV S channel, [0, 255]). CV across seams detects inconsistent colorfulness
    matching — some seams between similarly-saturated regions, others crossing
    a vivid/pastel boundary. Orthogonal to §5.86 (hue angle shift), §5.62
    (YCrCb chroma magnitude), and §5.38 (within-strip saturation spread).
    Returns 0.0 for grayscale, fewer than 2 seams, or mean_shift < 1.0.
    """
    if img is None or n_strips < 2 or boundary_px < 1:
        return 0.0
    if img.ndim != 3 or img.shape[2] != 3:
        return 0.0
    h = img.shape[0]
    if h < n_strips * 2:
        return 0.0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    sat = hsv[:, :, 1]  # [0, 255]
    strip_h = h // n_strips
    shifts = []
    for i in range(n_strips - 1):
        boundary_row = (i + 1) * strip_h
        above = sat[max(0, boundary_row - boundary_px):boundary_row]
        below = sat[boundary_row:min(h, boundary_row + boundary_px)]
        if above.size == 0 or below.size == 0:
            continue
        shifts.append(abs(float(above.mean()) - float(below.mean())))
    if len(shifts) < 2:
        return 0.0
    shifts = np.array(shifts, dtype=np.float32)
    mean_s = float(shifts.mean())
    if mean_s < 1.0:
        return 0.0
    return float(shifts.std() / mean_s)
