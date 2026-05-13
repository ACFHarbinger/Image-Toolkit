"""
backend/src/models/basic_wrapper.py
=====================================
Retrospective Background and Shading Correction (BaSiC).

New API (used by AnimeStitchPipeline):
    basic = BaSiCWrapper()
    flat, dark, baselines = basic.fit(images, luma_only=True)
    corrected_images      = basic.transform_stack(images, luma_only=True)
    basic.baselines       # per-frame broadcast-dimming scalars (N,)

Legacy API (backward-compatible):
    flat, dark            = basic.estimate_profiles(images)
    corrected             = basic.apply_correction(img)
    corrected_images      = basic.process_batch(images)
"""

import cv2
import numpy as np
import torch
from typing import List, Optional, Tuple


class BaSiCWrapper:
    """
    Estimates and removes spatially-varying shading (flat-field) and
    per-frame broadcast-dimming from a stack of anime frames.

    The algorithm is based on the BaSiC (Background and Shading Correction)
    approach:
        corrected_i = (raw_i / b_i - dark_field) / flat_field

    where:
        flat_field  -- common low-frequency gain map  (H, W)  ≈ 1.0
        dark_field  -- additive offset map            (H, W)  ≈ 0.0
        b_i         -- per-frame dimming scalar       scalar  ≈ 1.0
    """

    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # Public state (set after fit / estimate_profiles)
        self.flat_field: Optional[np.ndarray] = None  # (H, W, 3)  float32
        self.dark_field: Optional[np.ndarray] = None  # (H, W, 3)  float32
        self.baselines: Optional[np.ndarray] = None  # (N,)       float32

    # ------------------------------------------------------------------
    # New public API
    # ------------------------------------------------------------------

    def fit(
        self,
        images: List[np.ndarray],
        luma_only: bool = True,
        iterations: int = 6,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Estimate flat-field, dark-field, and per-frame dimming baselines.

        Parameters
        ----------
        images      : list of BGR uint8 arrays, all the same spatial size.
        luma_only   : if True, correct only the Y′ channel (faster, more
                      stable for anime where chroma rarely vignettes).
        iterations  : ALM refinement iterations.

        Returns
        -------
        flat_field  : (H, W, 3) float32 in [0.5, 2.0]
        dark_field  : (H, W, 3) float32 ≈ 0
        baselines   : (N,)      float32 per-frame dimming scalar
        """
        N = len(images)
        if N < 3:
            h, w = images[0].shape[:2]
            self.flat_field = np.ones((h, w, 3), np.float32)
            self.dark_field = np.zeros((h, w, 3), np.float32)
            self.baselines = np.ones(N, np.float32)
            return self.flat_field, self.dark_field, self.baselines

        # Normalise all frames to the first frame's spatial size before stacking.
        # Frames may have the same width but different heights after _normalise_widths
        # (which preserves aspect ratio), causing torch.stack to fail.
        # Downsample for flat-field estimation (shading is low-frequency)
        # 512x... is plenty for BaSiC estimation and saves GBs of VRAM.
        TARGET_W = 512
        ref_h_orig, ref_w_orig = images[0].shape[:2]
        target_h = int(ref_h_orig * TARGET_W / ref_w_orig)
        
        frames = []
        for img in images:
            # Resize to small target size
            small = cv2.resize(img, (TARGET_W, target_h), interpolation=cv2.INTER_AREA)
            t = torch.from_numpy(small).permute(2, 0, 1).float().to(self.device) / 255.0
            frames.append(t)
        X = torch.stack(frames)  # (N, 3, H, W)
        N, C, H, W = X.shape

        if luma_only:
            # Convert to Y′ only for flat-field estimation
            X_est = self._bgr_to_luma(X)  # (N, 1, H, W)
        else:
            X_est = X

        # --- ALM-style iterative estimation ---
        # Initialise flat-field F as the median (robust to moving characters)
        F, _ = torch.median(X_est, dim=0)  # (C', H, W)
        mean_F = F.mean(dim=(1, 2), keepdim=True).clamp(min=1e-6)
        F = F / mean_F  # normalise to mean=1

        # Per-frame dimming baseline: how bright is each frame relative to the flat-field?
        b = X_est.mean(dim=(2, 3)) / (F.mean() + 1e-6)  # (N, C')
        b = b.mean(dim=1)  # (N,) scalar per frame

        D = torch.zeros_like(F)  # dark field (kept zero)

        for _ in range(iterations):
            # Step 1: update F given b_i
            num = (X_est / b.view(N, 1, 1, 1).clamp(min=1e-4)).mean(dim=0)
            F = num - D
            mean_F = F.mean(dim=(1, 2), keepdim=True).clamp(min=1e-6)
            F = F / mean_F

            # Step 2: update b_i given F
            b_new = (X_est / (F.unsqueeze(0) + 1e-6)).mean(dim=(2, 3)).mean(dim=1)
            b = 0.7 * b + 0.3 * b_new  # momentum to stabilise

        # Normalise b relative to its own median so that:
        #   b_i = 1.0  → this frame has the same brightness as the median frame
        #   b_i < 0.75 → this frame is genuinely ≥25% darker than typical
        # Without this normalisation, a uniformly dark scene gives all b_i < 0.75
        # and triggers false "broadcast-dimming detected" warnings on every frame.
        b_median = b.median().clamp(min=1e-6)
        b = b / b_median

        # Smooth flat-field (shading is always low-frequency)
        F_np = (
            F.squeeze(0).permute(1, 2, 0).cpu().numpy()
            if F.dim() == 4
            else F.permute(1, 2, 0).cpu().numpy()
        )

        # If luma_only → F_np is (H,W,1), broadcast to (H,W,3)
        if F_np.shape[2] == 1:
            F_np = np.repeat(F_np, 3, axis=2)

        F_np = cv2.GaussianBlur(F_np, (31, 31), 0)
        F_np = np.clip(F_np, 0.5, 2.0)

        # Resize flat-field back to original frame size
        F_np = cv2.resize(F_np, (ref_w_orig, ref_h_orig), interpolation=cv2.INTER_LINEAR)
        self.flat_field = F_np.astype(np.float32)
        self.dark_field = np.zeros_like(self.flat_field)
        self.baselines = b.cpu().numpy().astype(np.float32)

        return self.flat_field, self.dark_field, self.baselines

    def transform_stack(
        self,
        images: List[np.ndarray],
        luma_only: bool = True,
    ) -> List[np.ndarray]:
        """
        Fit profiles on `images` then return the corrected stack.
        Calls fit() if it has not been called yet.
        """
        if self.flat_field is None or len(images) != (
            len(self.baselines) if self.baselines is not None else -1
        ):
            self.fit(images, luma_only=luma_only)

        return [
            self.apply_correction(img, baseline_override=float(self.baselines[i]))
            for i, img in enumerate(images)
        ]

    # ------------------------------------------------------------------
    # Legacy API (kept for backward compatibility)
    # ------------------------------------------------------------------

    def estimate_profiles(
        self,
        images: List[np.ndarray],
        iterations: int = 6,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Backward-compatible alias — calls fit() and returns (flat, dark)."""
        flat, dark, _ = self.fit(images, luma_only=False, iterations=iterations)
        return flat, dark

    def apply_correction(
        self,
        img: np.ndarray,
        baseline_override: Optional[float] = None,
    ) -> np.ndarray:
        """
        Apply BaSiC correction to a single BGR uint8 image.
        corrected = (img / b - dark) / flat
        """
        if self.flat_field is None:
            return img

        b = baseline_override if baseline_override is not None else 1.0
        img_f = img.astype(np.float32) / 255.0

        # Resize stored flat/dark fields to match the input frame if sizes differ
        # (occurs when frames have different heights after width-normalisation).
        flat = self.flat_field
        dark = self.dark_field
        h, w = img.shape[:2]
        if flat.shape[:2] != (h, w):
            flat = cv2.resize(flat, (w, h), interpolation=cv2.INTER_LINEAR)
            flat = np.clip(flat, 0.5, 2.0)
            dark = cv2.resize(dark, (w, h), interpolation=cv2.INTER_LINEAR)

        corrected = (img_f / max(b, 1e-4) - dark) / (flat + 1e-6)
        return np.clip(corrected * 255.0, 0, 255).astype(np.uint8)

    def process_batch(self, images: List[np.ndarray]) -> List[np.ndarray]:
        """Backward-compatible alias for transform_stack."""
        return self.transform_stack(images, luma_only=False)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _bgr_to_luma(x: torch.Tensor) -> torch.Tensor:
        """(N,3,H,W) BGR float32 → (N,1,H,W) Y′ float32."""
        b, g, r = x[:, 0:1], x[:, 1:2], x[:, 2:3]
        return 0.114 * b + 0.587 * g + 0.299 * r
