"""Framing-independent ground-truth score (2026-11-04).

``_compute_aligned_ssim`` stretches the output to the GT's width and height
and aligns without scale, so a 30 px crop moves it by -0.05..+0.06 and a
doubled collar can still score level with OpenCV. Here the output is
registered to the GT with a similarity (SIFT + RANSAC, polished by affine
ECC at half scale), then SSIM is taken on the eroded region both cover.
Coverage (share of the GT the output covers) is reported separately so a
tight crop is not rewarded or punished inside the SSIM.
"""

from __future__ import annotations

import cv2
import numpy as np
from skimage.metrics import structural_similarity

# Bump when the score changes; run_history.py rescore keys its cache on it.
FAIR_METRIC_VERSION = 2
_MIN_INLIERS = 8
_MIN_OVERLAP_PX = 5000
_ECC_SCALE = 0.5
_ECC_MIN_CC = 0.5


def register_to_gt(img: np.ndarray, gt: np.ndarray) -> np.ndarray | None:
    """2x3 map from ``img`` pixels into the GT frame, or None (best candidate
    by ECC preference; ``fair_gt_score`` scores every candidate)."""
    cands = _candidates(img, gt)
    return cands[-1] if cands else None


def _candidates(img: np.ndarray, gt: np.ndarray) -> list[np.ndarray]:
    """[SIFT similarity] or [SIFT similarity, ECC-polished affine]."""
    g1 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(gt, cv2.COLOR_BGR2GRAY)
    sift = cv2.SIFT_create(nfeatures=12000)
    k1, d1 = sift.detectAndCompute(g1, None)
    k2, d2 = sift.detectAndCompute(g2, None)
    if d1 is None or d2 is None or len(k1) < _MIN_INLIERS or len(k2) < _MIN_INLIERS:
        return []
    pairs = cv2.BFMatcher().knnMatch(d1, d2, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.8 * p[1].distance]
    if len(good) < _MIN_INLIERS:
        return []
    p1 = np.float32([k1[g.queryIdx].pt for g in good])
    p2 = np.float32([k2[g.trainIdx].pt for g in good])
    M, inl = cv2.estimateAffinePartial2D(
        p1, p2, method=cv2.RANSAC, ransacReprojThreshold=4.0, maxIters=10000
    )
    if M is None or inl is None or int(inl.sum()) < _MIN_INLIERS:
        return []
    if not 0.25 < float(np.hypot(*M[0, :2])) < 4.0:
        return []
    M = M.astype(np.float32)
    # Low-texture anime frames give few inliers; ECC polishes the estimate.
    s = _ECC_SCALE
    a = cv2.resize(g2, None, fx=s, fy=s, interpolation=cv2.INTER_AREA).astype(np.float32)
    b = cv2.resize(g1, None, fx=s, fy=s, interpolation=cv2.INTER_AREA).astype(np.float32)
    Mi = cv2.invertAffineTransform(M).astype(np.float32)  # ECC wants gt -> img
    Mi[:, 2] *= s
    try:
        cc, W = cv2.findTransformECC(
            a, b, Mi, cv2.MOTION_AFFINE,
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-5), None, 5,
        )
        if cc > _ECC_MIN_CC:
            W[:, 2] /= s
            return [M, cv2.invertAffineTransform(W).astype(np.float32)]
    except cv2.error:
        pass
    return [M]


def fair_gt_score(img: np.ndarray | None, gt: np.ndarray) -> dict:
    """``{"ssim": float | None, "cov": float}``; ssim None = unregistrable.

    Alignment is a nuisance parameter: the SIFT similarity and the ECC
    polish are both scored and the better one kept. The unmasked ECC can
    misconverge on outputs with black border wedges (asp_test92 2026-11-05:
    0.789 polished vs 0.878 SIFT-only, OpenCV's output 0.863 vs 0.880).
    """
    if img is None:
        return {"ssim": None, "cov": 0.0}
    best = {"ssim": None, "cov": 0.0}
    for M in _candidates(img, gt):
        r = _score_with(img, gt, M)
        if r["ssim"] is not None and (best["ssim"] is None or r["ssim"] > best["ssim"]):
            best = r
        elif best["ssim"] is None:
            best = r
    return best


def _score_with(img: np.ndarray, gt: np.ndarray, M: np.ndarray) -> dict:
    h, w = gt.shape[:2]
    out = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    valid_out = cv2.warpAffine(
        (img.max(axis=2) > 10).astype(np.uint8) * 255, M, (w, h), flags=cv2.INTER_NEAREST
    ) > 127
    valid_gt = gt.max(axis=2) > 10
    both = cv2.erode((valid_out & valid_gt).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    cov = float(both.sum() / max(1, valid_gt.sum()))
    if both.sum() < _MIN_OVERLAP_PX:
        return {"ssim": None, "cov": round(cov, 4)}
    a = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(gt, cv2.COLOR_BGR2GRAY)
    _, smap = structural_similarity(a, b, full=True, data_range=255)
    return {"ssim": round(float(smap[both].mean()), 4), "cov": round(cov, 4)}


__all__ = ["FAIR_METRIC_VERSION", "fair_gt_score", "register_to_gt"]
