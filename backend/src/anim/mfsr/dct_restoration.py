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

Vectorized: all blocks across the full canvas are stacked into a
(Bh, Bw, C, B, B) tensor so scipy.fft.dctn runs a single batched call
per frame per iteration rather than one Python call per 8x8 block.
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
    Multi-frame DCT iterative artifact reversal — vectorized over all blocks.

    All 8×8 blocks across the full canvas are stacked into a
    (Bh, Bw, C, B, B) tensor so scipy runs one batched DCT call per
    frame per iteration rather than one Python call per block.
    Falls back to a scalar loop if scipy is unavailable.

    Parameters
    ----------
    frames   : list of source BGR uint8 images.
    affines  : list of (2,3) float32 affines mapping each frame to canvas.
    canvas_h, canvas_w : canvas dimensions.
    quality  : assumed JPEG quality (used to scale the quant table).
    n_iter   : number of refinement sweeps.
    prior    : optional (canvas_h, canvas_w, 3) uint8 initial HR estimate.
    """
    if not frames:
        raise ValueError("restore_dct: empty frame list")

    if not _SCIPY_OK:
        return _restore_dct_scalar(
            frames, affines, canvas_h, canvas_w, quality, n_iter, prior
        )

    B = DCT_BLOCK_SIZE  # 8
    q_table = _quant_table_array(quality)  # (8, 8)

    # Warp every source frame onto the canvas (uint8, cached).
    warped = [
        _warp_to_canvas(f, M, canvas_h, canvas_w)
        for f, M in zip(frames, affines)
    ]

    # Pad dimensions to multiples of B.
    pad_h = (-canvas_h) % B
    pad_w = (-canvas_w) % B
    H_p = canvas_h + pad_h
    W_p = canvas_w + pad_w
    Bh = H_p // B
    Bw = W_p // B

    # Per-frame valid-block masks: True where ≥ half the block's pixels are covered.
    def _valid_blocks(w: np.ndarray) -> np.ndarray:
        v = (w.max(axis=2) > 0).astype(np.uint8)
        vp = np.pad(v, ((0, pad_h), (0, pad_w)), mode="constant")
        # (H_p, W_p) → (Bh, Bw, B, B) → sum over block → (Bh, Bw) bool
        vb = vp.reshape(Bh, B, Bw, B).transpose(0, 2, 1, 3)
        return vb.sum(axis=(-2, -1)) >= (B * B) // 2

    valid_masks = [_valid_blocks(w) for w in warped]

    # Initial HR estimate.
    if prior is not None and prior.shape[:2] == (canvas_h, canvas_w):
        estimate = prior.astype(np.float64).copy()
    else:
        accum0 = np.zeros((canvas_h, canvas_w, 3), dtype=np.float64)
        cnt0 = np.zeros((canvas_h, canvas_w), dtype=np.float64)
        for w in warped:
            accum0 += w.astype(np.float64)
            cnt0 += (w.max(axis=2) > 0).astype(np.float64)
        estimate = np.clip(accum0 / np.maximum(cnt0[:, :, None], 1.0), 0.0, 255.0)

    # Pad estimate to multiples of B.
    estimate_p: np.ndarray = (
        np.pad(estimate, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
        if (pad_h or pad_w) else estimate.copy()
    )

    def _to_blocks(img: np.ndarray) -> np.ndarray:
        """(H_p, W_p, C) float64 → (Bh, Bw, C, B, B), centered on 128."""
        # reshape interleaves spatial and block dims; transpose collects them.
        blocks = img.reshape(Bh, B, Bw, B, 3).transpose(0, 2, 4, 1, 3)
        return np.ascontiguousarray(blocks) - 128.0

    def _from_blocks(blocks: np.ndarray) -> np.ndarray:
        """(Bh, Bw, C, B, B) float64 → (H_p, W_p, C), adding 128 back."""
        spatial = np.ascontiguousarray((blocks + 128.0).transpose(0, 3, 1, 4, 2))
        return spatial.reshape(H_p, W_p, 3)

    relax = 0.6
    base_w = 1e-3  # tiny weight keeps unvisited blocks at their current estimate value

    # Precompute per-frame clip bounds (lo, hi) once — constant across iterations.
    # np.clip(est_dct, lo, hi) is mathematically equivalent to the original
    # mismatch/fancy-index logic: when quant levels agree est_dct is already
    # inside [lo, hi], so clip is a no-op; when they disagree, clip projects the
    # estimate coefficient into the source's quantisation cell.
    print(f"[MFSR/DCT] Precomputing clip bounds for {len(warped)} source frames…")
    frame_bounds: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []
    for w_uint8, v_ok in zip(warped, valid_masks):
        w_f = np.pad(
            w_uint8.astype(np.float64),
            ((0, pad_h), (0, pad_w), (0, 0)),
            mode="edge",
        )
        sd = dctn(_to_blocks(w_f), norm="ortho", axes=(-2, -1))
        sq = np.round(sd / q_table) * q_table   # nearest quant cell centre in coeff units
        lo = sq - 0.5 * q_table
        hi = sq + 0.5 * q_table
        # Cache valid-rows index for masked accumulation (avoids repeated astype).
        v_float = v_ok.astype(np.float64)
        frame_bounds.append((lo, hi, v_ok, v_float))
    del warped  # uint8 source frames no longer needed

    # Pre-allocate the clip output buffer — reused every frame every iteration.
    refined_buf = np.empty((Bh, Bw, 3, B, B), dtype=np.float64)

    for it in range(n_iter):
        # One DCT of the current estimate per iteration.
        est_dct = dctn(_to_blocks(estimate_p), norm="ortho", axes=(-2, -1))

        # Accumulate: start at est_dct × base_w so unvisited blocks stay put.
        accum_dct = est_dct * base_w
        weight = np.full((Bh, Bw), base_w, dtype=np.float64)

        for lo, hi, v_ok, v_float in frame_bounds:
            # Project estimate into each source's quant cell (vectorised clip).
            np.clip(est_dct, lo, hi, out=refined_buf)
            # Accumulate only rows where this source frame has valid coverage.
            accum_dct[v_ok] += refined_buf[v_ok]
            weight += v_float

        # One IDCT to convert the averaged DCT back to spatial.
        w_safe = np.maximum(weight, base_w)[:, :, np.newaxis, np.newaxis, np.newaxis]
        new_p = _from_blocks(idctn(accum_dct / w_safe, norm="ortho", axes=(-2, -1)))

        # Damped update — prevents DCT-domain ringing.
        estimate_p = (1.0 - relax) * estimate_p + relax * new_p

        if it == 0 or (it + 1) % 5 == 0 or it + 1 == n_iter:
            print(f"[MFSR/DCT]   iter {it + 1}/{n_iter} done.")

    return np.clip(estimate_p[:canvas_h, :canvas_w], 0.0, 255.0).astype(np.uint8)


def _restore_dct_scalar(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    canvas_h: int,
    canvas_w: int,
    quality: int = 75,
    n_iter: int = DCT_ITERATIONS,
    prior: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Scalar fallback (no scipy) — slow for large canvases."""
    B = DCT_BLOCK_SIZE
    q_table_scaled = _quant_table_array(quality)

    warped = [_warp_to_canvas(f, M, canvas_h, canvas_w) for f, M in zip(frames, affines)]
    valids = [(w.max(axis=2) > 0).astype(np.uint8) for w in warped]

    if prior is not None and prior.shape[:2] == (canvas_h, canvas_w):
        estimate = prior.astype(np.float64).copy()
    else:
        accum = np.zeros((canvas_h, canvas_w, 3), dtype=np.float64)
        count = np.zeros((canvas_h, canvas_w), dtype=np.float64)
        for w, v in zip(warped, valids):
            accum += w.astype(np.float64)
            count += v.astype(np.float64)
        estimate = accum / np.maximum(count, 1.0)[:, :, None]

    pad_h = (-canvas_h) % B
    pad_w = (-canvas_w) % B
    if pad_h or pad_w:
        estimate_p = np.pad(estimate, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
    else:
        estimate_p = estimate.copy()
    H_p, W_p, _ = estimate_p.shape

    for it in range(n_iter):
        weight_map = np.ones((H_p, W_p), dtype=np.float64) * 1e-3
        accum_blocks = np.zeros_like(estimate_p)

        for w_img, v_img in zip(warped, valids):
            w_p = np.pad(
                w_img, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge"
            ).astype(np.float64)
            v_p = np.pad(v_img, ((0, pad_h), (0, pad_w)), mode="constant")

            for by in range(0, H_p, B):
                for bx in range(0, W_p, B):
                    if v_p[by:by + B, bx:bx + B].sum() < (B * B) // 2:
                        continue
                    for c in range(3):
                        src_block = w_p[by:by + B, bx:bx + B, c]
                        est_block = estimate_p[by:by + B, bx:bx + B, c]
                        src_dct = dct_block(src_block - 128.0)
                        est_dct = dct_block(est_block - 128.0)
                        src_quant = np.round(src_dct / q_table_scaled)
                        est_quant = np.round(est_dct / q_table_scaled)
                        refined_dct = est_dct.copy()
                        mismatch = est_quant != src_quant
                        lo = (src_quant - 0.5) * q_table_scaled
                        hi = (src_quant + 0.5) * q_table_scaled
                        refined_dct[mismatch] = np.clip(
                            est_dct[mismatch], lo[mismatch], hi[mismatch]
                        )
                        accum_blocks[by:by + B, bx:bx + B, c] += (
                            idct_block(refined_dct) + 128.0
                        )
                    weight_map[by:by + B, bx:bx + B] += 1.0

        new_estimate = accum_blocks / weight_map[:, :, None]
        relax = 0.6
        estimate_p = (1.0 - relax) * estimate_p + relax * new_estimate

        if it == 0 or (it + 1) % 5 == 0 or it + 1 == n_iter:
            print(f"[MFSR/DCT]   iter {it + 1}/{n_iter} done.")

    return np.clip(estimate_p[:canvas_h, :canvas_w], 0.0, 255.0).astype(np.uint8)


__all__ = [
    "dct_block",
    "idct_block",
    "quantize",
    "restore_dct",
]
