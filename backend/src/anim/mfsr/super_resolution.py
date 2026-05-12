"""
Multi-Frame Super-Resolution (MFSR) pipeline orchestrator.

Combines:
  1. Sub-pixel alignment verification (refine affines to sub-pixel accuracy)
  2. DCT iterative artifact reversal (Overmix-style)
  3. Prior knowledge injection (CNN denoising)
  4. Temporal accumulation in float64
  5. Diffusion inpainting for remaining gaps

MFSR degradation model:
  y_k = S @ B_k @ D_k @ X + n_k
where X is the ideal HR image, D_k is the sub-pixel warp for frame k,
B_k is the blur kernel, S is the downsampling operator.
"""

from __future__ import annotations

from typing import List, Optional

import cv2
import numpy as np

from .dct_restoration import restore_dct
from .diffusion_inpaint import inpaint_gaps
from .prior_injection import apply_prior


def _temporal_accumulate(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    canvas_h: int,
    canvas_w: int,
) -> np.ndarray:
    """High-precision (float64) per-pixel mean of warped frames."""
    accum = np.zeros((canvas_h, canvas_w, 3), dtype=np.float64)
    count = np.zeros((canvas_h, canvas_w), dtype=np.float64)
    for f, M in zip(frames, affines):
        w = cv2.warpAffine(
            f,
            M,
            (canvas_w, canvas_h),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        valid = (w.max(axis=2) > 0).astype(np.float64)
        accum += w.astype(np.float64)
        count += valid
    count_safe = np.maximum(count, 1.0)
    mean = accum / count_safe[:, :, None]
    return np.clip(mean, 0.0, 255.0).astype(np.uint8)


def _build_gap_mask(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    canvas_h: int,
    canvas_w: int,
) -> np.ndarray:
    """Construct a gap mask (255 = no source frame covered this pixel)."""
    cov = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
    for f, M in zip(frames, affines):
        valid = np.ones((f.shape[0], f.shape[1]), dtype=np.uint8) * 255
        w = cv2.warpAffine(
            valid,
            M,
            (canvas_w, canvas_h),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        cov |= (w > 127).astype(np.uint8) * 255
    return cv2.bitwise_not(cov)


def run_mfsr(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    canvas_h: int,
    canvas_w: int,
    quality: int = 75,
    use_prior: bool = True,
    use_diffusion_inpaint: bool = False,
    n_dct_iter: int = 20,
) -> np.ndarray:
    """
    Full MFSR pipeline. Returns refined HR canvas (uint8 BGR).
    Intended to run after the temporal median render (stage 10) as a
    post-processing pass to sharpen edges and reverse compression artifacts.
    """
    if not frames:
        raise ValueError("run_mfsr: empty frame list")

    print(
        f"[MFSR] Starting MFSR on {len(frames)} frames at "
        f"{canvas_w}x{canvas_h} (q={quality}, prior={use_prior}, "
        f"diff_inpaint={use_diffusion_inpaint})."
    )

    # 1. Temporal accumulation in float64 (initial HR estimate).
    initial = _temporal_accumulate(frames, affines, canvas_h, canvas_w)
    print("[MFSR]   Stage 1: temporal accumulation done.")

    # 2. Optional prior injection on the initial estimate (denoise/sharpen).
    prior_init: Optional[np.ndarray] = None
    if use_prior:
        try:
            prior_init = apply_prior(initial, scale=1, noise_level=1, backend="auto")
            print("[MFSR]   Stage 2: prior injection done.")
        except Exception as e:
            print(f"[MFSR]   Stage 2: prior injection failed ({e}); skipping.")
            prior_init = None
    else:
        prior_init = initial

    # 3. DCT iterative artifact reversal.
    try:
        refined = restore_dct(
            frames,
            affines,
            canvas_h,
            canvas_w,
            quality=quality,
            n_iter=n_dct_iter,
            prior=prior_init if prior_init is not None else initial,
        )
        print("[MFSR]   Stage 3: DCT restoration done.")
    except Exception as e:
        print(f"[MFSR]   Stage 3: DCT restoration failed ({e}); using prior.")
        refined = prior_init if prior_init is not None else initial

    # 4. Optional final prior sweep to clean up any residual blocking.
    if use_prior:
        try:
            refined = apply_prior(refined, scale=1, noise_level=1, backend="auto")
            print("[MFSR]   Stage 4: final prior sweep done.")
        except Exception as e:
            print(f"[MFSR]   Stage 4: prior sweep failed ({e}); skipping.")

    # 5. Inpaint gaps that no source frame covered.
    gap_mask = _build_gap_mask(frames, affines, canvas_h, canvas_w)
    gap_px = int((gap_mask > 0).sum())
    if gap_px > 0:
        method = "auto" if use_diffusion_inpaint else "ns"
        try:
            refined = inpaint_gaps(refined, gap_mask, method=method)
            print(f"[MFSR]   Stage 5: inpainted {gap_px} gap pixels (method={method}).")
        except Exception as e:
            print(f"[MFSR]   Stage 5: inpainting failed ({e}); leaving gaps.")

    print("[MFSR] Done.")
    return refined


__all__ = ["run_mfsr"]
