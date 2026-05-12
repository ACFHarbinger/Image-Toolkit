"""
Pairwise feature matching for anime stitching.

Each function is standalone (no class state).  ``loftr_wrapper`` is passed in
explicitly when LoFTR matching is enabled.
"""

from __future__ import annotations

import gc
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch

from .constants import (
    _MATCH_EDGE_CROP,
    _MAX_DX_DRIFT_RATIO,
    _MIN_TEMPLATE_SCORE,
    _PC_CONF_THRESHOLD,
)
from .stateless import _highpass, _luma


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

    if best_conf < _MIN_TEMPLATE_SCORE:
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

    if response < _PC_CONF_THRESHOLD:
        return None, 0.0

    dx, dy = float(shift[0]), float(shift[1])
    M = np.array([[1, 0, dx], [0, 1, dy]], np.float32)
    return M, float(response)


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
) -> Optional[Dict]:
    """
    Try to match frame i to frame j. Optimized for vertical anime pans.
    """
    img_i, img_j = frames[i], frames[j]
    m_i = bg_masks[i]
    m_j = bg_masks[j]

    # ── Pre-match Edge Crop (Discard distortion) ──
    ec_h = int(H * _MATCH_EDGE_CROP)
    ec_w = int(W * _MATCH_EDGE_CROP)

    match_img_i = img_i[ec_h:-ec_h, ec_w:-ec_w]
    match_img_j = img_j[ec_h:-ec_h, ec_w:-ec_w]
    match_m_i = m_i[ec_h:-ec_h, ec_w:-ec_w] if m_i is not None else None
    match_m_j = m_j[ec_h:-ec_h, ec_w:-ec_w] if m_j is not None else None

    def _is_valid(M):
        if M is None:
            return False
        dx = abs(M[0, 2])
        if dx > W * _MAX_DX_DRIFT_RATIO:
            return False
        return True

    M: Optional[np.ndarray] = None
    mean_conf = 0.0
    actual_pts_i: Optional[np.ndarray] = None
    actual_pts_j: Optional[np.ndarray] = None

    # ── Attempt 1: LoFTR ───────────────────────────────────────────────────
    if use_loftr and loftr_wrapper is not None:
        try:
            pts1, pts2, conf = loftr_wrapper.match(match_img_i, match_img_j)
            if len(pts1) >= 30:
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

                if len(pts1) >= 20:
                    if motion_model == "translation":
                        dxs = pts2[:, 0] - pts1[:, 0]
                        dys = pts2[:, 1] - pts1[:, 1]
                        dx, dy = np.median(dxs), np.median(dys)
                        M = np.array([[1, 0, dx], [0, 1, dy]], np.float32)
                        mean_conf = float(conf.mean())
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
                        print(
                            f"[Stitch]   {i}→{j}: LoFTR dx={M[0, 2]:.1f} dy={M[1, 2]:.1f} conf={mean_conf:.3f} (pts={len(pts1)})"
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
            print(
                f"[Stitch]   {i}→{j}: TemplateMatch dy={M[1, 2]:.1f} conf={mean_conf:.3f}"
            )

    # ── Attempt 3a: Masked phase correlation ───────────────────────────────
    if M is None:
        M_pc, c_pc = _phase_correlate(
            match_img_i, match_img_j, match_m_i, match_m_j, use_mask=True
        )
        if _is_valid(M_pc) and c_pc > 0.25:
            M, mean_conf = M_pc, c_pc
            print(
                f"[Stitch]   {i}→{j}: PhaseCorr(masked) dx={M[0, 2]:.1f} dy={M[1, 2]:.1f} conf={mean_conf:.3f}"
            )

    # ── Attempt 3b: Unmasked phase correlation (uniform-bg fallback) ──────
    if M is None:
        M_pc2, c_pc2 = _phase_correlate(
            match_img_i, match_img_j, None, None, use_mask=False
        )
        if _is_valid(M_pc2) and c_pc2 > 0.15:
            M, mean_conf = M_pc2, c_pc2
            print(
                f"[Stitch]   {i}→{j}: PhaseCorr(unmasked) dx={M[0, 2]:.1f} dy={M[1, 2]:.1f} conf={mean_conf:.3f}"
            )

    if M is None:
        print(f"[Stitch]   {i}→{j}: all methods failed — skipping edge.")
        return None

    # For a translation-only pipeline, we enforce identity rotation/scale here
    M_transl = np.eye(2, 3, dtype=np.float32)
    M_transl[0, 2] = M[0, 2]
    M_transl[1, 2] = M[1, 2]
    M = M_transl

    # Build anchor points for the BA residuals
    if actual_pts_i is not None and actual_pts_j is not None:
        pts_i = actual_pts_i
        pts_j = actual_pts_j
    else:
        pts_i = _sample_bg_points(m_i, H, W, n=200)
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
    "_match_pair",
    "_pairwise_match",
]
