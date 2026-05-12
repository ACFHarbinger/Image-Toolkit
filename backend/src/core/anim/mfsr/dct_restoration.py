"""
DCT-based iterative JPEG/MPEG artifact reversal (Overmix algorithm).

For each source frame, for each 8x8 block:
  1. Extract the same 8x8 region from the current HR estimate.
  2. Forward DCT both the source block and the estimate block.
  3. Quantize the estimate's DCT coefficients using the JPEG quant table.
  4. Where quantized estimate == source coefficient, replace the source
     (low-precision) coefficient with the unquantized estimate coefficient.
  5. Inverse DCT and accumulate into the updated estimate.

After all frames, normalize and return the refined estimate.
"""

from __future__ import annotations

from typing import List, Optional

import cv2
import numpy as np

try:
    from scipy.fft import dctn, idctn
    _SCIPY_OK = True
except ImportError:
    _SCIPY_OK = False

from ..constants import (
    DCT_BLOCK_SIZE,
    DCT_ITERATIONS,
    DCT_QUANT_TABLE_LUMINANCE,
)


def dct_block(block: np.ndarray) -> np.ndarray:
    """2D DCT-II of an 8x8 block."""
    if _SCIPY_OK:
        return dctn(block.astype(np.float64), norm="ortho")
    # Fallback: OpenCV DCT (only supports even-sized matrices, which 8x8 is)
    return cv2.dct(block.astype(np.float64))


def idct_block(block: np.ndarray) -> np.ndarray:
    """2D IDCT-II of an 8x8 block."""
    if _SCIPY_OK:
        return idctn(block, norm="ortho")
    return cv2.idct(block.astype(np.float64))


def quantize(coeffs: np.ndarray, q_table: np.ndarray, quality: int = 75) -> np.ndarray:
    """Quantize DCT coefficients using a quality-scaled quant table."""
    quality = int(max(1, min(100, quality)))
    if quality >= 50:
        scale = (100 - quality) / 50
    else:
        scale = 50 / quality
    scaled = q_table.reshape(8, 8) * scale
    # JPEG spec: round, clamp to >=1
    scaled = np.maximum(1.0, np.round(scaled))
    return np.round(coeffs / scaled), scaled


def _quant_table_array(quality: int = 75) -> np.ndarray:
    """Get the JPEG-scaled quantization table (8x8)."""
    q = np.asarray(DCT_QUANT_TABLE_LUMINANCE, dtype=np.float64).reshape(8, 8)
    quality = int(max(1, min(100, quality)))
    scale = (100 - quality) / 50 if quality >= 50 else 50 / quality
    return np.maximum(1.0, np.round(q * scale))


def _warp_to_canvas(
    frame: np.ndarray,
    M: np.ndarray,
    canvas_h: int,
    canvas_w: int,
    flags: int = cv2.INTER_LANCZOS4,
) -> np.ndarray:
    """Warp a frame onto the canvas with constant black borders."""
    return cv2.warpAffine(
        frame,
        M,
        (canvas_w, canvas_h),
        flags=flags,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def restore_dct(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    canvas_h: int,
    canvas_w: int,
    quality: int = 75,
    n_iter: int = DCT_ITERATIONS,
    prior: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Multi-frame DCT iterative artifact reversal.

    Parameters
    ----------
    frames : list of source BGR uint8 images.
    affines : list of (2,3) float32 affines mapping each frame onto the canvas.
    canvas_h, canvas_w : canvas dimensions.
    quality : assumed JPEG quality of the source frames (used to size the
        per-coefficient confidence intervals).
    n_iter : how many DCT refinement sweeps to perform.
    prior : optional (canvas_h, canvas_w, 3) uint8 image used as the initial
        HR estimate.  If None, the per-pixel mean of the warped frames is used.

    Returns
    -------
    Refined HR canvas (uint8 BGR).
    """
    if not frames:
        raise ValueError("restore_dct: empty frame list")

    B = DCT_BLOCK_SIZE
    q_table_scaled = _quant_table_array(quality)

    # 1) Warp every frame to canvas once (cache).
    warped = [_warp_to_canvas(f, M, canvas_h, canvas_w) for f, M in zip(frames, affines)]
    valids = [(w.max(axis=2) > 0).astype(np.uint8) for w in warped]

    # 2) Initial estimate.
    if prior is not None and prior.shape[:2] == (canvas_h, canvas_w):
        estimate = prior.astype(np.float64).copy()
    else:
        accum = np.zeros((canvas_h, canvas_w, 3), dtype=np.float64)
        count = np.zeros((canvas_h, canvas_w), dtype=np.float64)
        for w, v in zip(warped, valids):
            accum += w.astype(np.float64)
            count += v.astype(np.float64)
        count_safe = np.maximum(count, 1.0)
        estimate = accum / count_safe[:, :, None]

    # 3) Pad estimate to multiples of B
    pad_h = (-canvas_h) % B
    pad_w = (-canvas_w) % B
    if pad_h or pad_w:
        estimate_p = np.pad(
            estimate, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge"
        )
    else:
        estimate_p = estimate.copy()
    H_p, W_p, _ = estimate_p.shape

    for it in range(n_iter):
        # For each frame, refine estimate block-by-block where it's valid.
        new_estimate = estimate_p.copy()
        weight_map = np.ones((H_p, W_p), dtype=np.float64) * 1e-3
        accum_blocks = np.zeros_like(estimate_p)

        for w_img, v_img in zip(warped, valids):
            w_p = (
                np.pad(w_img, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
                .astype(np.float64)
            )
            v_p = np.pad(v_img, ((0, pad_h), (0, pad_w)), mode="constant")

            for by in range(0, H_p, B):
                for bx in range(0, W_p, B):
                    if v_p[by : by + B, bx : bx + B].sum() < (B * B) // 2:
                        # mostly black/out-of-frame block — skip
                        continue
                    for c in range(3):
                        src_block = w_p[by : by + B, bx : bx + B, c]
                        est_block = estimate_p[by : by + B, bx : bx + B, c]

                        # Center on 128 for JPEG semantics
                        src_centered = src_block - 128.0
                        est_centered = est_block - 128.0

                        src_dct = dct_block(src_centered)
                        est_dct = dct_block(est_centered)

                        # Quantized representation that the source would have produced
                        src_quant = np.round(src_dct / q_table_scaled)
                        est_quant = np.round(est_dct / q_table_scaled)

                        # Keep the estimate coefficient whenever its quant level
                        # agrees with the source's quant level; otherwise snap
                        # the estimate into the source coefficient's quant cell
                        # (clamp to the nearest cell-boundary in the source).
                        refined_dct = est_dct.copy()
                        mismatch = est_quant != src_quant
                        # When they disagree, project the estimate coefficient
                        # back into the source's quant interval.
                        lo = (src_quant - 0.5) * q_table_scaled
                        hi = (src_quant + 0.5) * q_table_scaled
                        refined_dct[mismatch] = np.clip(
                            est_dct[mismatch], lo[mismatch], hi[mismatch]
                        )

                        refined_block = idct_block(refined_dct) + 128.0
                        accum_blocks[by : by + B, bx : bx + B, c] += refined_block
                    weight_map[by : by + B, bx : bx + B] += 1.0

        new_estimate = accum_blocks / weight_map[:, :, None]
        # Damped update — relax toward the new estimate (avoids oscillation)
        relax = 0.6
        estimate_p = (1.0 - relax) * estimate_p + relax * new_estimate

    refined = estimate_p[:canvas_h, :canvas_w]
    refined = np.clip(refined, 0.0, 255.0).astype(np.uint8)
    return refined


__all__ = [
    "dct_block",
    "idct_block",
    "quantize",
    "restore_dct",
]
