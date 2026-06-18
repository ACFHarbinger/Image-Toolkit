"""
Pairwise feature matching for anime stitching.

Each function is standalone (no class state).  ``loftr_wrapper`` is passed in
explicitly when LoFTR matching is enabled.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import gc
import os
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

from backend.src.constants import (
    MATCH_EDGE_CROP,
    MAX_DX_DRIFT_RATIO,
    MIN_TEMPLATE_SCORE,
    PC_CONF_THRESHOLD,
)
from .stateless import _highpass, _luma

# §1.3E — Similarity-mode flag.  When ON, matched affines are projected to
# their best-fit 4-DOF similarity (scale + rotation + translation, no shear)
# instead of being stripped to translation-only.  Useful for zoom-pan sequences
# where the camera both pans and zooms simultaneously (e.g. test5).
# Default OFF to preserve backward-compatible translation-only behaviour.
_SIMILARITY_MODE: bool = os.environ.get("ASP_SIMILARITY_MODE", "0") != "0"

# §1.36: LoFTR translation consensus spread filter.
# Rejects the LoFTR translation estimate when per-match displacements have high MAD
# (median absolute deviation) around the median — indicative of texture confusion
# between repeated background elements, or character motion polluting matches.
# Set to 0.0 to disable (default); recommend 30.0 for real sequences.
_MATCH_SPREAD_CEIL: float = float(os.environ.get("ASP_MATCH_SPREAD_CEIL", "0.0"))

# §1.38: LoFTR background match ratio gate.
# Rejects the LoFTR edge when background keypoints are too small a fraction of all
# LoFTR matches — indicates a foreground-dominated scene where the surviving bg
# keypoints are sparse and their median displacement is noisy.
# Set to 0.0 to disable (default); recommend 0.15 for real sequences.
_LOFTR_BG_RATIO_MIN: float = float(os.environ.get("ASP_LOFTR_BG_RATIO_MIN", "0.0"))


def _extract_similarity(M: np.ndarray) -> np.ndarray:
    """§1.3E — Project a full 2×3 affine to its best-fit 4-DOF similarity.

    A similarity transform has the form ``[[a, b, tx], [-b, a, ty]]``.  A
    general affine ``[[a, b, tx], [c, d, ty]]`` decomposes as::

        a_sym = (a + d) / 2   (average of diagonal — symmetric part)
        b_sym = (b - c) / 2   (antisymmetric off-diagonal — rotation/scale)

    This is the closed-form least-squares projection onto the similarity
    manifold (Procrustes for 2-D conformal maps).  Shear (asymmetric
    off-diagonal component) is discarded because feature matchers
    (LoFTR, RoMa) cannot reliably distinguish camera shear from
    perspective distortion at anime-panel scales.

    Parameters
    ----------
    M : (2, 3) float32 affine matrix.

    Returns
    -------
    (2, 3) float32 similarity matrix with the same translation as M.
    """
    a = float(M[0, 0])
    b = float(M[0, 1])
    c = float(M[1, 0])
    d = float(M[1, 1])
    a_sym = (a + d) / 2.0
    b_sym = (b - c) / 2.0
    out = np.eye(2, 3, dtype=np.float32)
    out[0, 0] = a_sym
    out[0, 1] = b_sym
    out[1, 0] = -b_sym
    out[1, 1] = a_sym
    out[0, 2] = float(M[0, 2])
    out[1, 2] = float(M[1, 2])
    return out


def _compute_translation_spread(
    pts_i: np.ndarray,
    pts_j: np.ndarray,
) -> "tuple[float, float]":
    """§1.36: Per-axis MAD of LoFTR displacement estimates around their median.

    When LoFTR finds many correspondences but they disagree on the translation
    (e.g., bimodal distribution from foreground / background confusions), the median
    displacement is unreliable. A high MAD flags this ambiguity before the edge is
    committed to the graph.

    Parameters
    ----------
    pts_i, pts_j : (N, 2) float32 — matched keypoint coordinates in frames i and j.

    Returns
    -------
    (mad_dx, mad_dy) : pair of floats, each ≥ 0.
        0.0 when N ≤ 1 (no spread to compute).
    """
    if len(pts_i) <= 1:
        return 0.0, 0.0
    dxs = pts_j[:, 0] - pts_i[:, 0]
    dys = pts_j[:, 1] - pts_i[:, 1]
    mad_dx = float(np.median(np.abs(dxs - np.median(dxs))))
    mad_dy = float(np.median(np.abs(dys - np.median(dys))))
    return mad_dx, mad_dy


def _compute_bg_match_ratio(n_bg_pts: int, n_total_pts: int) -> float:
    """§1.38: Fraction of LoFTR matches that land on background pixels.

    When most LoFTR matches fall on foreground characters, the handful of
    surviving background matches produce a noisy median displacement estimate.
    This function quantifies how bg-clean the match set is so the caller can
    reject the edge when the ratio is too low.

    Parameters
    ----------
    n_bg_pts    : number of matches whose endpoints are both on background (mask > 127).
    n_total_pts : total LoFTR matches before bg filtering.

    Returns
    -------
    float in [0, 1].  Returns 0.0 when *n_total_pts* is 0 (avoids ZeroDivisionError).
    """
    if n_total_pts <= 0:
        return 0.0
    return float(n_bg_pts) / float(n_total_pts)


def _template_match(
    img_i: np.ndarray,
    img_j: np.ndarray,
    m_i: Optional[np.ndarray],
    m_j: Optional[np.ndarray],
    H: int,
    slice_h: int = 256,
    max_search_frac: float = 0.8,
    direction_sign: int = 0,
    max_dy_frac: float = 0.70,
) -> Tuple[Optional[np.ndarray], float]:
    """
    Bidirectional template match: handles both upward and downward pans.

    direction_sign: +1 = only search downward (dy > 0),
                    -1 = only search upward (dy < 0),
                     0 = search both (default).
    max_dy_frac:    reject any dy whose |dy| > H * max_dy_frac; enforces a
                    minimum overlap fraction between adjacent frames so that
                    near-zero-overlap false matches (uniform background regions
                    found at the far edge of the search window) are discarded.
    """
    g_i = _luma(img_i)
    g_j = _luma(img_j)
    search_h = int(H * max_search_frac)
    max_dy = H * max_dy_frac

    best_dy = 0.0
    best_conf = 0.0

    # Config A: search i_bottom in j_top  -> gives dy > 0 (downward pan)
    # Config B: search i_top in j_bottom  -> gives dy < 0 (upward pan)
    all_configs = [
        {"strip_y": H - slice_h, "roi_y": 0, "sign": 1},
        {"strip_y": 0, "roi_y": H - search_h, "sign": -1},
    ]
    # Filter configs by requested direction
    test_configs = (
        [c for c in all_configs if c["sign"] == direction_sign]
        if direction_sign != 0
        else all_configs
    )

    for config in test_configs:
        strip_y = config["strip_y"]
        roi_y0 = max(0, config["roi_y"])
        roi_y1 = min(H, roi_y0 + search_h)

        tmpl = g_i[strip_y : strip_y + slice_h, :].copy()
        mask = m_i[strip_y : strip_y + slice_h, :] if m_i is not None else None
        roi = g_j[roi_y0:roi_y1, :]

        if roi.shape[0] < slice_h:
            continue
        if tmpl.std() < 2.0:
            continue

        try:
            res = cv2.matchTemplate(roi, tmpl, cv2.TM_CCORR_NORMED, mask=mask)
            _, v, _, loc = cv2.minMaxLoc(res)

            if v > best_conf and v > 0.4:
                # i_strip_y matches j_y at (roi_y0 + loc[1])
                # dy = T_j - T_i = strip_y - (roi_y0 + loc[1])
                candidate_dy = float(strip_y - (roi_y0 + loc[1]))
                if abs(candidate_dy) > max_dy:
                    # Near-zero overlap — discard (likely false match on uniform bg)
                    continue
                best_conf = v
                best_dy = candidate_dy
        except Exception:
            continue

    if best_conf < MIN_TEMPLATE_SCORE:
        return None, 0.0

    M = np.array([[1, 0, 0], [0, 1, best_dy]], np.float32)
    return M, best_conf


def _phase_correlate(
    img_i: np.ndarray,
    img_j: np.ndarray,
    m_i: Optional[np.ndarray],
    m_j: Optional[np.ndarray],
    use_mask: bool = True,
) -> Tuple[Optional[np.ndarray], float]:
    """
    Phase correlation on high-pass filtered Y' channels.

    use_mask: when True (default) zero out foreground pixels before
              correlating so that moving characters don't bias the shift.
              Set False for scenes where the background is so uniform that
              masking removes nearly all texture — the character itself then
              provides the dominant phase signal.
    """
    g_i = _highpass(_luma(img_i)).astype(np.float32)
    g_j = _highpass(_luma(img_j)).astype(np.float32)

    if use_mask:
        if m_i is not None:
            g_i[m_i == 0] = 0.0
        if m_j is not None:
            g_j[m_j == 0] = 0.0

    try:
        hann = cv2.createHanningWindow(g_i.shape[::-1], cv2.CV_32F)
        shift, response = cv2.phaseCorrelate(g_i, g_j, hann)
    except Exception:
        return None, 0.0

    if response < PC_CONF_THRESHOLD:
        return None, 0.0

    dx, dy = shift[0], shift[1]
    M = np.array([[1, 0, dx], [0, 1, dy]], np.float32)
    return M, response


def _sample_bg_points(
    mask: Optional[np.ndarray], H: int, W: int, n: int = 200
) -> np.ndarray:
    """Sample up to n (x,y) pixel coordinates from the background mask."""
    if mask is None:
        ys = np.random.randint(0, H, n)
        xs = np.random.randint(0, W, n)
    else:
        ys_bg, xs_bg = np.where(mask > 0)
        if len(ys_bg) == 0:
            ys = np.random.randint(0, H, n)
            xs = np.random.randint(0, W, n)
        else:
            idx = np.random.choice(len(ys_bg), min(n, len(ys_bg)), replace=False)
            ys, xs = ys_bg[idx], xs_bg[idx]
    return np.stack([xs, ys], axis=1).astype(np.float32)


def _sample_bg_points_grid(
    mask: Optional[np.ndarray],
    H: int,
    W: int,
    n: int = 50,
    grid: Tuple[int, int] = (4, 4),
) -> np.ndarray:
    """
    Spatially-distributed background point sampler.

    Divides the image into a grid and draws points from each cell, ensuring
    coverage across all quadrants.  Non-LoFTR fallback edges use this instead
    of random sampling (P1.5 — W7 fix) so the BA solver receives spatially
    distributed anchor points rather than centre-biased random ones.
    """
    gr, gc = grid
    pts_list: List[np.ndarray] = []
    per_cell = max(1, n // (gr * gc))

    for r in range(gr):
        for c in range(gc):
            y0 = r * H // gr
            y1 = (r + 1) * H // gr
            x0 = c * W // gc
            x1 = (c + 1) * W // gc

            if mask is None:
                ys = np.random.randint(y0, max(y0 + 1, y1), per_cell)
                xs = np.random.randint(x0, max(x0 + 1, x1), per_cell)
            else:
                cell_mask = mask[y0:y1, x0:x1]
                ys_bg, xs_bg = np.where(cell_mask > 0)
                if len(ys_bg) == 0:
                    ys = np.random.randint(y0, max(y0 + 1, y1), per_cell)
                    xs = np.random.randint(x0, max(x0 + 1, x1), per_cell)
                else:
                    idx = np.random.choice(
                        len(ys_bg), min(per_cell, len(ys_bg)), replace=False
                    )
                    ys = ys_bg[idx] + y0
                    xs = xs_bg[idx] + x0

            pts_list.append(np.stack([xs, ys], axis=1).astype(np.float32))

    if not pts_list:
        return _sample_bg_points(mask, H, W, n)
    return np.concatenate(pts_list, axis=0)


def _segment_guided_match(
    img_i: np.ndarray,
    img_j: np.ndarray,
    mask_i: Optional[np.ndarray] = None,
    mask_j: Optional[np.ndarray] = None,
    n_colors: int = 16,
    min_seg_px: int = 400,
    min_segs: int = 6,
) -> Tuple[Optional[np.ndarray], float]:
    """
    P2.9 — Segment-guided matching (AnimeInterp technique).

    Segments both frames into flat-color contiguous regions using mean-shift
    filtering + connected components.  For each background region in frame i,
    finds the closest color-and-position match in frame j, then computes the
    centroid displacement.  The median over all matched-region displacements
    gives a robust translation estimate even when LoFTR and phase correlation
    fail on uniform-background anime cells.

    Returns (M, confidence) or (None, 0.0).
    """
    h, w = img_i.shape[:2]

    def _segment(
        img: np.ndarray, mask: Optional[np.ndarray]
    ) -> Tuple[np.ndarray, np.ndarray]:
        # Downscale for speed (mean-shift is O(N²))
        scale = min(1.0, 320.0 / max(h, w))
        img_s = cv2.resize(
            img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
        )
        # Mean-shift segmentation into flat color regions
        ms = cv2.pyrMeanShiftFiltering(img_s, sp=8, sr=30)
        # Quantise colors to reduce fragmentation
        ms_flat = ms.reshape(-1, 3).astype(np.float32)
        _, labels_flat, centers = cv2.kmeans(
            ms_flat,
            n_colors,
            None,
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0),
            3,
            cv2.KMEANS_PP_CENTERS,
        )
        quantized = centers[labels_flat.flatten()].reshape(img_s.shape).astype(np.uint8)
        # Connected components on quantized image (one CC per flat region)
        gray_q = cv2.cvtColor(quantized, cv2.COLOR_BGR2GRAY)
        _, cc_map = cv2.connectedComponents(gray_q, connectivity=8)
        # Scale CC map back to original size
        cc_full = cv2.resize(
            cc_map.astype(np.int32), (w, h), interpolation=cv2.INTER_NEAREST
        )
        return cc_full, centers[labels_flat.reshape(img_s.shape[:2])]

    try:
        cc_i, _ = _segment(img_i, mask_i)
        cc_j, _ = _segment(img_j, mask_j)
    except Exception:
        return None, 0.0

    def _seg_stats(img: np.ndarray, cc: np.ndarray, mask: Optional[np.ndarray]):
        stats = {}
        for label in np.unique(cc):
            if label == 0:
                continue
            seg_px = cc == label
            if mask is not None:
                seg_px = seg_px & (mask > 127)
            count = int(seg_px.sum())
            if count < min_seg_px:
                continue
            ys, xs = np.where(seg_px)
            cy, cx = float(ys.mean()), float(xs.mean())
            color = img[seg_px].astype(np.float32).mean(axis=0)  # (3,)
            stats[label] = {"cy": cy, "cx": cx, "color": color, "count": count}
        return stats

    segs_i = _seg_stats(img_i, cc_i, mask_i)
    segs_j = _seg_stats(img_j, cc_j, mask_j)

    if len(segs_i) < min_segs or len(segs_j) < min_segs:
        return None, 0.0

    # Build color arrays for matching
    labels_j = list(segs_j.keys())
    colors_j = np.array([segs_j[l]["color"] for l in labels_j], dtype=np.float32)

    displacements = []
    for li, si in segs_i.items():
        c_i = si["color"]
        # L2 color distance to all segments in j
        color_dists = np.linalg.norm(colors_j - c_i[np.newaxis], axis=1)
        # Position distance (normalised by image size)
        pos_dists = np.array(
            [
                np.sqrt(
                    ((segs_j[lj]["cy"] - si["cy"]) / h) ** 2
                    + ((segs_j[lj]["cx"] - si["cx"]) / w) ** 2
                )
                for lj in labels_j
            ],
            dtype=np.float32,
        )
        # Combined score: low color distance + nearby position
        score = color_dists / 256.0 + 2.0 * pos_dists
        best_idx = int(np.argmin(score))
        if score[best_idx] > 0.5:  # too dissimilar — skip
            continue
        sj = segs_j[labels_j[best_idx]]
        dy = sj["cy"] - si["cy"]
        dx = sj["cx"] - si["cx"]
        displacements.append((dx, dy))

    if len(displacements) < min_segs:
        return None, 0.0

    dxs = np.array([d[0] for d in displacements])
    dys = np.array([d[1] for d in displacements])
    dx_med = float(np.median(dxs))
    dy_med = float(np.median(dys))

    M = np.array([[1, 0, dx_med], [0, 1, dy_med]], dtype=np.float32)
    # Confidence: fraction of displacement pairs within 20px of the median
    residuals = np.sqrt((dxs - dx_med) ** 2 + (dys - dy_med) ** 2)
    conf = float((residuals < 20.0).mean()) * 0.5  # cap at 0.5 (lower than LoFTR)
    return M, max(conf, 0.15)


def _match_pair(
    frames: List[np.ndarray],
    bg_masks: List[Optional[np.ndarray]],
    i: int,
    j: int,
    H: int,
    W: int,
    loftr_wrapper=None,
    use_loftr: bool = True,
    motion_model: str = "translation",
    aliked_wrapper=None,
    roma_wrapper=None,
) -> Optional[Dict]:
    """
    Try to match frame i to frame j. Optimized for vertical anime pans.
    """
    img_i, img_j = frames[i], frames[j]
    m_i = bg_masks[i]
    m_j = bg_masks[j]

    # ── Pre-match Edge Crop (Discard distortion) ──
    ec_h = int(H * MATCH_EDGE_CROP)
    ec_w = int(W * MATCH_EDGE_CROP)

    match_img_i = img_i[ec_h:-ec_h, ec_w:-ec_w]
    match_img_j = img_j[ec_h:-ec_h, ec_w:-ec_w]
    match_m_i = m_i[ec_h:-ec_h, ec_w:-ec_w] if m_i is not None else None
    match_m_j = m_j[ec_h:-ec_h, ec_w:-ec_w] if m_j is not None else None

    def _is_valid(M):
        if M is None:
            return False
        dx = abs(M[0, 2])
        if dx > W * MAX_DX_DRIFT_RATIO:
            return False
        return True

    M: Optional[np.ndarray] = None
    mean_conf = 0.0
    actual_pts_i: Optional[np.ndarray] = None
    actual_pts_j: Optional[np.ndarray] = None
    _loftr_bg_pts: int = 0  # track how many BG keypoints LoFTR found (for 1b trigger)

    # ── Attempt 1: LoFTR ───────────────────────────────────────────────────
    if use_loftr and loftr_wrapper is not None:
        try:
            pts1, pts2, conf = loftr_wrapper.match(match_img_i, match_img_j)
            if len(pts1) >= 30:
                n_loftr_total = len(pts1)  # capture before bg filtering (§1.38)
                if match_m_i is not None and match_m_j is not None:
                    y1, x1 = pts1[:, 1].astype(int), pts1[:, 0].astype(int)
                    y2, x2 = pts2[:, 1].astype(int), pts2[:, 0].astype(int)
                    h, w = match_m_i.shape[:2]
                    valid = (
                        (x1 >= 0)
                        & (x1 < w)
                        & (y1 >= 0)
                        & (y1 < h)
                        & (x2 >= 0)
                        & (x2 < w)
                        & (y2 >= 0)
                        & (y2 < h)
                    )
                    if valid.any():
                        m1_vals = match_m_i[y1[valid], x1[valid]]
                        m2_vals = match_m_j[y2[valid], x2[valid]]
                        bg_mask = (m1_vals > 127) & (m2_vals > 127)
                        indices = np.where(valid)[0][bg_mask]
                        pts1, pts2, conf = (
                            pts1[indices],
                            pts2[indices],
                            conf[indices],
                        )
                _loftr_bg_pts = len(pts1)
                # §1.38: Reject LoFTR edge when bg matches are a small fraction of
                # total matches — fg-dominated pairs produce noisy median displacement.
                if _LOFTR_BG_RATIO_MIN > 0.0:
                    _bg_ratio = _compute_bg_match_ratio(_loftr_bg_pts, n_loftr_total)
                    if _bg_ratio < _LOFTR_BG_RATIO_MIN:
                        logger.debug(
                            f"[Stitch]   {i}→{j}: LoFTR rejected "
                            f"(bg_ratio={_bg_ratio:.2f} < {_LOFTR_BG_RATIO_MIN:.2f}, "
                            f"bg_pts={_loftr_bg_pts}/{n_loftr_total})"
                        )
                        pts1 = np.empty((0, 2), np.float32)

                if len(pts1) >= 20:
                    if motion_model == "translation":
                        dxs = pts2[:, 0] - pts1[:, 0]
                        dys = pts2[:, 1] - pts1[:, 1]
                        dx, dy = np.median(dxs), np.median(dys)
                        M = np.array([[1, 0, dx], [0, 1, dy]], np.float32)
                        mean_conf = float(conf.mean())
                        # §1.36: Reject when per-match displacement spread is too high —
                        # high MAD means LoFTR matches disagree on the translation
                        # (foreground/background confusion, bimodal distribution).
                        if _MATCH_SPREAD_CEIL > 0.0:
                            _mad_dx, _mad_dy = _compute_translation_spread(pts1, pts2)
                            if max(_mad_dx, _mad_dy) > _MATCH_SPREAD_CEIL:
                                M = None
                                logger.debug(
                                    f"[Stitch]   {i}→{j}: LoFTR rejected "
                                    f"(spread mad_dx={_mad_dx:.1f} mad_dy={_mad_dy:.1f} "
                                    f"> {_MATCH_SPREAD_CEIL:.0f}px)"
                                )
                    else:
                        M_raw, inliers = cv2.estimateAffine2D(
                            pts1, pts2, method=cv2.RANSAC, ransacReprojThreshold=5.0
                        )
                        if _is_valid(M_raw):
                            inl = inliers.ravel().astype(bool)
                            if inl.sum() >= 15:
                                M, mean_conf = (
                                    M_raw.astype(np.float32),
                                    float(conf[inl].mean()),
                                )

                    if M is not None:
                        actual_pts_i = pts1 + [ec_w, ec_h]
                        actual_pts_j = pts2 + [ec_w, ec_h]
                        logger.debug(
                            f"[Stitch]   {i}→{j}: LoFTR dx={M[0, 2]:.1f} dy={M[1, 2]:.1f} conf={mean_conf:.3f} (pts={len(pts1)})"
                        )

        except Exception:
            pass

    # ── Attempt 1b: ALIKED + LightGlue (P2.3) ─────────────────────────────
    # Trigger when LoFTR returned < 20 background keypoints on a flat/sparse
    # scene.  ALIKED's deformable descriptor head detects keypoints at anime
    # line-art edges that LoFTR misses in low-texture regions.
    if M is None and aliked_wrapper is not None and _loftr_bg_pts < 20:
        try:
            M_alg, c_alg, pts_alg_i, pts_alg_j = aliked_wrapper.get_translation(
                match_img_i, match_img_j, match_m_i, match_m_j
            )
            if M_alg is not None and _is_valid(M_alg) and len(pts_alg_i) >= 15:
                M, mean_conf = M_alg, c_alg
                actual_pts_i = pts_alg_i + [ec_w, ec_h]
                actual_pts_j = pts_alg_j + [ec_w, ec_h]
                logger.debug(
                    f"[Stitch]   {i}→{j}: ALIKED+LG dx={M[0, 2]:.1f} dy={M[1, 2]:.1f} "
                    f"conf={mean_conf:.3f} (pts={len(pts_alg_i)})"
                )
        except Exception:
            pass

    # ── Attempt 2: Template Match (Fallback) ───────────────────────────────
    if M is None:
        M_tm, c_tm = _template_match(
            match_img_i, match_img_j, match_m_i, match_m_j, match_img_i.shape[0]
        )
        if M_tm is not None and c_tm > 0.6:
            M, mean_conf = M_tm, c_tm
            logger.debug(
                f"[Stitch]   {i}→{j}: TemplateMatch dy={M[1, 2]:.1f} conf={mean_conf:.3f}"
            )

    # ── Attempt 3a: Masked phase correlation ───────────────────────────────
    if M is None:
        M_pc, c_pc = _phase_correlate(
            match_img_i, match_img_j, match_m_i, match_m_j, use_mask=True
        )
        if _is_valid(M_pc) and c_pc > 0.25:
            M, mean_conf = M_pc, c_pc
            logger.debug(
                f"[Stitch]   {i}→{j}: PhaseCorr(masked) dx={M[0, 2]:.1f} dy={M[1, 2]:.1f} conf={mean_conf:.3f}"
            )

    # ── Attempt 3b: Unmasked phase correlation (uniform-bg fallback) ──────
    if M is None:
        M_pc2, c_pc2 = _phase_correlate(
            match_img_i, match_img_j, None, None, use_mask=False
        )
        if _is_valid(M_pc2) and c_pc2 > 0.15:
            M, mean_conf = M_pc2, c_pc2
            logger.debug(
                f"[Stitch]   {i}→{j}: PhaseCorr(unmasked) dx={M[0, 2]:.1f} dy={M[1, 2]:.1f} conf={mean_conf:.3f}"
            )

    # ── Attempt 4: Segment-guided matching (P2.9, AnimeInterp technique) ──
    # Segment both frames into flat-color regions via mean-shift + connected
    # components, match regions by colour/position proximity, and take the
    # median centroid displacement as the translation estimate.  Robust on
    # low-texture anime cells where all above methods fail.
    if M is None:
        try:
            M_sg, c_sg = _segment_guided_match(
                match_img_i, match_img_j, match_m_i, match_m_j
            )
            if M_sg is not None and _is_valid(M_sg):
                M, mean_conf = M_sg, c_sg
                logger.debug(
                    f"[Stitch]   {i}→{j}: SegmentGuided dx={M[0, 2]:.1f} dy={M[1, 2]:.1f} conf={mean_conf:.3f}"
                )
        except Exception:
            pass

    # ── Attempt 5: RoMa v2 dense warp (P2.8) ─────────────────────────────
    # DINOv2 features are style-agnostic and work on flat anime cells where
    # all other matchers fail.  Last resort before declaring the edge dead.
    if M is None and roma_wrapper is not None:
        try:
            M_roma, c_roma = roma_wrapper.match_translation(
                match_img_i, match_img_j, match_m_i, match_m_j
            )
            if M_roma is not None and _is_valid(M_roma):
                M, mean_conf = M_roma, c_roma
                logger.debug(
                    f"[Stitch]   {i}→{j}: RoMa dx={M[0, 2]:.1f} dy={M[1, 2]:.1f} conf={mean_conf:.3f}"
                )
        except Exception:
            pass

    if M is None:
        logger.info(f"[Stitch]   {i}→{j}: all methods failed — skipping edge.")
        return None

    # §1.3E: when ASP_SIMILARITY_MODE=1, project to best-fit 4-DOF similarity
    # (scale + rotation + translation, shear discarded).  Default: strip to
    # translation-only to preserve backward-compatible behaviour.
    if _SIMILARITY_MODE:
        M = _extract_similarity(M)
    else:
        M_transl = np.eye(2, 3, dtype=np.float32)
        M_transl[0, 2] = M[0, 2]
        M_transl[1, 2] = M[1, 2]
        M = M_transl

    # Build anchor points for the BA residuals.
    # Convention: M[1,2] = dy where dy = y_j - y_i (forward-shift: LoFTR/PC).
    # Canvas placement: ty_j = ty_i - dy, so residual pi_global = pj_global
    # requires pts_j = pts_i + M[:2, 2].
    if actual_pts_i is not None and actual_pts_j is not None:
        pts_i = actual_pts_i
        pts_j = actual_pts_j
    else:
        # P1.5: use spatially-distributed grid sampling (4×4, n=50) for non-LoFTR edges
        # to avoid centre-biased random anchor points that dilute the BA signal (W7).
        pts_i = _sample_bg_points_grid(m_i, H, W, n=50, grid=(4, 4))
        pts_j = pts_i + M[:2, 2]

    return {
        "i": i,
        "j": j,
        "M": M,
        "pts_i": pts_i,
        "pts_j": pts_j,
        "weight": mean_conf,
    }


def _pairwise_match(
    frames: List[np.ndarray],
    bg_masks: List[Optional[np.ndarray]],
    loftr_wrapper=None,
    use_loftr: bool = True,
    motion_model: str = "translation",
    aliked_wrapper=None,
    roma_wrapper=None,
) -> List[Dict]:
    """
    Build pairwise correspondence edges using LoFTR -> template match -> PC fallback.
    Adds consecutive (i->i+1) plus skip-pair (i->i+2, i->i+3) edges.
    """
    N = len(frames)
    H, W = frames[0].shape[:2]

    # Build list of (i, j) pairs to try
    pairs: List[Tuple[int, int]] = []
    for i in range(N - 1):
        pairs.append((i, i + 1))
    for i in range(N - 2):
        pairs.append((i, i + 2))  # skip-1
    for i in range(N - 3):
        pairs.append((i, i + 3))  # skip-2

    edges: List[Dict] = []
    for idx, (i, j) in enumerate(pairs):
        edge = _match_pair(
            frames,
            bg_masks,
            i,
            j,
            H,
            W,
            loftr_wrapper=loftr_wrapper,
            use_loftr=use_loftr,
            motion_model=motion_model,
            aliked_wrapper=aliked_wrapper,
            roma_wrapper=roma_wrapper,
        )
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
        if edge is not None:
            edges.append(edge)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    return edges


__all__ = [
    "_template_match",
    "_phase_correlate",
    "_sample_bg_points",
    "_sample_bg_points_grid",
    "_segment_guided_match",
    "_match_pair",
    "_pairwise_match",
    "_extract_similarity",
    "_compute_translation_spread",
]