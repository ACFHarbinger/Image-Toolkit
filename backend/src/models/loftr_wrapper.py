"""
backend/src/models/loftr_wrapper.py
======================================
LoFTR feature matcher wrapper.

New API (used by AnimeStitchPipeline):
    wrapper = LoFTRWrapper()
    pts1, pts2, conf = wrapper.match_masked(img1, img2, mask1, mask2)
    M, mean_conf     = wrapper.get_affine_partial(img1, img2, mask1, mask2)
    # M: (2,3) float32 affine matrix  or  None

Legacy API (backward-compatible):
    pts1, pts2, conf = wrapper.match(img1, img2)
    H                = wrapper.get_transform(img1, img2)   # (3,3) homography
"""

import cv2
import numpy as np
import torch
torch.backends.cudnn.benchmark = False
import kornia.feature as KF
from typing import Optional, Tuple

# LoFTR optimal input size (divisible by 32, close to model sweet-spot)
_LOFTR_H = 320
_LOFTR_W = 448
_MIN_INLIERS = 20


class LoFTRWrapper:
    """
    Wraps kornia's LoFTR for dense feature matching between pairs of images.
    Particularly robust on anime frames with flat colours / repetitive texture
    where classical SIFT/ORB detectors struggle.
    """

    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.matcher = None

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def offload(self):
        if self.matcher is not None:
            self.matcher.cpu()
            if torch.cuda.is_available(): torch.cuda.empty_cache()

    def load_model(self):
        if self.matcher is None:
            print("[LoFTR] Loading outdoor model …")
            self.matcher = KF.LoFTR(pretrained="outdoor").to(self.device)
        else:
            self.matcher.to(self.device)
            self.matcher.eval()

    # ------------------------------------------------------------------
    # Internal: raw LoFTR inference
    # ------------------------------------------------------------------

    def _run_loftr(
        self,
        gray1: np.ndarray,
        gray2: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Run LoFTR on two grayscale uint8 images.
        Returns (pts1, pts2, confidence) in the original image coordinate system.
        """
        self.load_model()
        h1, w1 = gray1.shape
        h2, w2 = gray2.shape

        # Resize to LoFTR sweet-spot (must be divisible by 32)
        def _resize_for_loftr(g, th, tw):
            return cv2.resize(g, (tw, th), interpolation=cv2.INTER_AREA)

        g1r = _resize_for_loftr(gray1, _LOFTR_H, _LOFTR_W)
        g2r = _resize_for_loftr(gray2, _LOFTR_H, _LOFTR_W)

        t1 = torch.from_numpy(g1r).float()[None, None].to(self.device) / 255.0
        t2 = torch.from_numpy(g2r).float()[None, None].to(self.device) / 255.0

        with torch.no_grad():
            corr = self.matcher({"image0": t1, "image1": t2})
        del t1, t2

        pts1 = corr["keypoints0"].detach().cpu().numpy().copy()
        pts2 = corr["keypoints1"].detach().cpu().numpy().copy()
        conf = corr["confidence"].detach().cpu().numpy().copy()
        del corr

        # Scale back to original resolution
        pts1[:, 0] *= w1 / _LOFTR_W
        pts1[:, 1] *= h1 / _LOFTR_H
        pts2[:, 0] *= w2 / _LOFTR_W
        pts2[:, 1] *= h2 / _LOFTR_H

        return pts1, pts2, conf

    # ------------------------------------------------------------------
    # New API
    # ------------------------------------------------------------------

    def match_masked(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        mask1: Optional[np.ndarray] = None,  # uint8 (H,W) 255=valid
        mask2: Optional[np.ndarray] = None,
        conf_thresh: float = 0.4,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Match img1 ↔ img2 with LoFTR, then filter by confidence and
        optional background masks (removes correspondences that land on
        foreground characters which move between frames).

        Returns
        -------
        pts1, pts2 : (K, 2) float32 in original pixel coordinates
        conf       : (K,)   float32
        """
        g1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        pts1, pts2, conf = self._run_loftr(g1, g2)

        # Confidence filter
        keep = conf > conf_thresh

        # Background-mask filter
        if mask1 is not None and len(pts1) > 0:
            h1, w1 = mask1.shape[:2]
            ix = np.clip(pts1[:, 0].astype(int), 0, w1 - 1)
            iy = np.clip(pts1[:, 1].astype(int), 0, h1 - 1)
            keep &= mask1[iy, ix] > 0

        if mask2 is not None and len(pts2) > 0:
            h2, w2 = mask2.shape[:2]
            jx = np.clip(pts2[:, 0].astype(int), 0, w2 - 1)
            jy = np.clip(pts2[:, 1].astype(int), 0, h2 - 1)
            keep &= mask2[jy, jx] > 0

        return pts1[keep], pts2[keep], conf[keep]

    def get_affine_partial(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        mask1: Optional[np.ndarray] = None,
        mask2: Optional[np.ndarray] = None,
        min_inliers: int = _MIN_INLIERS,
    ) -> Tuple[Optional[np.ndarray], float]:
        """
        Estimate a 4-DoF affine-partial transform (translation + rotation + uniform scale)
        from img1 to img2 using MAGSAC++ robust estimation.

        Returns
        -------
        M          : (2, 3) float32 affine matrix, or None if estimation failed.
        mean_conf  : mean correspondence confidence of inliers (float).
        """
        pts1, pts2, conf = self.match_masked(img1, img2, mask1, mask2)

        if len(pts1) < min_inliers:
            return None, 0.0

        # estimateAffinePartial2D only accepts cv2.RANSAC (8) and cv2.LMEDS (4).
        # USAC flags (USAC_MAGSAC, USAC_DEFAULT, …) are only valid for
        # findHomography / findFundamentalMat — passing them here raises
        # "Unknown or unsupported robust estimation method" on all OpenCV builds.
        # We use RANSAC with a tight reprojection threshold to get good robustness.
        M_raw, inliers = cv2.estimateAffinePartial2D(
            pts1,
            pts2,
            method=cv2.RANSAC,
            ransacReprojThreshold=2.0,
            confidence=0.999,
            maxIters=10_000,
        )

        if M_raw is None or inliers is None:
            return None, 0.0

        inl_mask = inliers.ravel().astype(bool)
        if inl_mask.sum() < min_inliers:
            return None, 0.0

        return M_raw.astype(np.float32), float(conf[inl_mask].mean())

    # ------------------------------------------------------------------
    # Legacy API (backward-compatible)
    # ------------------------------------------------------------------

    def match(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Basic LoFTR match without mask filtering.
        Returns: (pts1, pts2, confidence).
        """
        g1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        return self._run_loftr(g1, g2)

    def get_transform(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
    ) -> Optional[np.ndarray]:
        """
        Estimate a (3, 3) homography between img1 and img2.
        Returns None if estimation fails.  Kept for backward compatibility.
        """
        pts1, pts2, conf = self.match(img1, img2)
        if len(pts1) < 4:
            return None
        keep = conf > 0.5
        if keep.sum() < 4:
            return None
        H, status = cv2.findHomography(pts1[keep], pts2[keep], cv2.RANSAC, 5.0)
        return H if (status is not None and status.sum() > 4) else None
