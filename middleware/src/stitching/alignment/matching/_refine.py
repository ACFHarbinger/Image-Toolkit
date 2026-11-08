"""Sub-pixel refinement of a pairwise translation.

The HF EfficientLoFTR port returns coarse-grid matches on a 640x480 resize,
so its median translation is quantised to ~16 px at 1080p and often
collapses to 0 on pans (2026-11-04: median 11 px off OpenCV's confident
pairs, 53% off by more than 10 px). This module takes candidate
translations (matcher median, a SIFT + RANSAC estimate), refines each
with pyramid ECC on the background, and keeps the best correlation.

Convention matches ``_match_pair``: ``t = p_j - p_i``.
"""

from __future__ import annotations

import os

import cv2
import numpy as np

# ECC pyramid scales (coarse to fine); the finest sets precision.
ECC_SCALES = (0.125, 0.25, 0.5)
# Below this ECC correlation a refined hypothesis is not trusted.
MIN_ECC_CC = 0.6
# A pyramid level smaller than this (short side, px) is skipped.
_MIN_LEVEL_PX = 96
# SIFT works at this scale of the frame.
SIFT_SCALE = 0.5
_MIN_BG_FRAC = 0.05


def refine_enabled() -> bool:
    """``ASP_EDGE_REFINE=0`` keeps the raw matcher translation."""
    return os.environ.get("ASP_EDGE_REFINE", "1") != "0"


def keep_unverified() -> bool:
    """``ASP_EDGE_DROP_UNVERIFIED=1`` drops an edge refinement could not
    verify (asp_test84 kept template edges 500 px off). Off by default: on
    the 2026-11-04 subset it fixed asp_test04/43/95 but broke asp_test46."""
    return os.environ.get("ASP_EDGE_DROP_UNVERIFIED", "0") != "1"


def _gray(img: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return g.astype(np.float32)


def _bg(mask: np.ndarray | None, shape: tuple[int, int]) -> np.ndarray | None:
    """uint8 {0,1} background mask, or None when it would leave too little."""
    if mask is None or mask.shape[:2] != shape:
        return None
    m = (mask > 127).astype(np.uint8)
    return m if m.mean() >= _MIN_BG_FRAC else None


def _ecc_pyramid(
    gi: np.ndarray, gj: np.ndarray, mi: np.ndarray | None, t0: tuple[float, float]
) -> tuple[np.ndarray, float] | None:
    """Translation ECC from ``t0`` over ``ECC_SCALES``. Returns (t, cc)."""
    t = np.asarray(t0, np.float32)
    cc = 0.0
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-4)
    short = min(gi.shape[:2])
    scales = [s for s in ECC_SCALES if s * short >= _MIN_LEVEL_PX] or [ECC_SCALES[-1]]
    for s in scales:
        a = cv2.resize(gi, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        b = cv2.resize(gj, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        m = (
            None
            if mi is None
            else cv2.resize(mi, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_NEAREST)
        )
        W = np.array([[1, 0, t[0] * s], [0, 1, t[1] * s]], np.float32)
        try:
            cc, W = cv2.findTransformECC(a, b, W, cv2.MOTION_TRANSLATION, crit, m, 5)
        except cv2.error:
            return None
        t = W[:, 2] / s
    return t, float(cc)


def sift_translation(
    img_i: np.ndarray,
    img_j: np.ndarray,
    mask_i: np.ndarray | None,
    mask_j: np.ndarray | None,
) -> tuple[float, float] | None:
    """SIFT + ratio test + RANSAC similarity; the inliers' median shift."""
    s = SIFT_SCALE
    gi = cv2.resize(_gray(img_i), None, fx=s, fy=s, interpolation=cv2.INTER_AREA).astype(np.uint8)
    gj = cv2.resize(_gray(img_j), None, fx=s, fy=s, interpolation=cv2.INTER_AREA).astype(np.uint8)

    def m(mask, g):
        b = _bg(mask, mask.shape[:2]) if mask is not None else None
        return None if b is None else cv2.resize(b, (g.shape[1], g.shape[0]), interpolation=cv2.INTER_NEAREST)

    sift = cv2.SIFT_create(nfeatures=4000)
    ki, di = sift.detectAndCompute(gi, m(mask_i, gi))
    kj, dj = sift.detectAndCompute(gj, m(mask_j, gj))
    if di is None or dj is None or len(ki) < 8 or len(kj) < 8:
        return None
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(di, dj, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    if len(good) < 12:
        return None
    pi = np.float32([ki[g.queryIdx].pt for g in good])
    pj = np.float32([kj[g.trainIdx].pt for g in good])
    _, inl = cv2.estimateAffinePartial2D(pi, pj, method=cv2.RANSAC, ransacReprojThreshold=2.0)
    if inl is None or int(inl.sum()) < 12:
        return None
    d = (pj - pi)[inl.ravel().astype(bool)]
    dx, dy = np.median(d, axis=0) / s
    return float(dx), float(dy)


def refine_translation(
    img_i: np.ndarray,
    img_j: np.ndarray,
    mask_i: np.ndarray | None,
    mask_j: np.ndarray | None,
    candidates: list[tuple[float, float]],
    use_sift: bool = True,
) -> tuple[float, float, float] | None:
    """Best ECC-refined translation among ``candidates`` (+ SIFT).

    Returns ``(dx, dy, cc)`` or None when no hypothesis reaches
    ``MIN_ECC_CC``.
    """
    gi, gj = _gray(img_i), _gray(img_j)
    hyps = [tuple(map(float, c)) for c in candidates if c is not None]
    if use_sift:
        st = sift_translation(img_i, img_j, mask_i, mask_j)
        if st is not None:
            hyps.append(st)
    uniq: list[tuple[float, float]] = []
    for h in hyps:
        if all(abs(h[0] - u[0]) + abs(h[1] - u[1]) > 2.0 for u in uniq):
            uniq.append(h)
    # Background-masked first; unmasked only when the mask leaves nothing
    # that correlates (BiRefNet can call most of an animated frame "fg").
    mi = _bg(mask_i, gi.shape)
    for mask in ([mi, None] if mi is not None else [None]):
        best: tuple[float, float, float] | None = None
        for h in uniq:
            r = _ecc_pyramid(gi, gj, mask, h)
            if r is None:
                continue
            t, cc = r
            if cc >= MIN_ECC_CC and (best is None or cc > best[2]):
                best = (float(t[0]), float(t[1]), cc)
        if best is not None:
            return best
    return None


__all__ = ["keep_unverified", "refine_enabled", "refine_translation", "sift_translation", "MIN_ECC_CC"]
