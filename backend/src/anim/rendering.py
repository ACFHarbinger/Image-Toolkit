"""
Temporal rendering: median, first-frame, and Laplacian-blend renderers.

All functions are standalone — they take ``frames``, ``affines`` and (where
applicable) ``bg_masks`` as explicit arguments.
"""

from __future__ import annotations

import os
import warnings
from typing import List, Optional, Tuple

import cv2
import numpy as np

from backend.src.constants import (
    MEDIAN_MIN_SAMPLES,
    RENDERING_FADE_ROWS,
    LANCZOS_BLEED,
    MAX_SAFE_GAIN_DEV,
)
from .canvas import _detect_scroll_axis
from .stateless import _laplacian_blend

# A5 — Foreground-excluded temporal median.  When enabled, foreground (character)
# pixels are excluded from the per-pixel median so the background PLATE never
# averages the character's differing animation poses into a translucent ghost.
# Where a canvas pixel has NO background sample across any frame (the character
# is always there), the median falls back to all geometrically-valid pixels so
# no holes appear.  Stage 11 then composites the re-posed foreground on top.
# Set ASP_FG_EXCLUDE_MEDIAN=0 to disable (A/B comparison).
_FG_EXCLUDE_MEDIAN = os.environ.get("ASP_FG_EXCLUDE_MEDIAN", "1") != "0"


def _compute_sequential_color_gains(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    bg_masks: Optional[List[Optional[np.ndarray]]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Sequential per-frame color gain/bias via overlap-zone photometric matching.

    Frame 0 is the photometric anchor. Each subsequent frame is corrected to
    match its predecessor's color in their shared canvas overlap zone, then the
    correction is chained so all frames end up photometrically consistent.

    Samples multiple horizontal stripes spread across the overlap zone and uses
    the per-channel median across stripes. When bg_masks are provided, only
    background pixels (mask > 127) are included, preventing foreground
    character movement from corrupting the photometric reference.
    """
    N = len(frames)
    gains = np.ones((N, 3), dtype=np.float32)
    biases = np.zeros((N, 3), dtype=np.float32)

    N_BLOCKS_Y = 4
    N_BLOCKS_X = 4
    MIN_BG_PX = 200

    for i in range(1, N):
        H_i, W_i = frames[i].shape[:2]
        H_p, W_p = frames[i - 1].shape[:2]
        ty_i = float(affines[i][1, 2])
        ty_p = float(affines[i - 1][1, 2])
        tx_i = float(affines[i][0, 2])
        tx_p = float(affines[i - 1][0, 2])

        # Canvas overlap bounding box
        ov_top = max(ty_i, ty_p)
        ov_bot = min(ty_i + H_i, ty_p + H_p)
        ov_left = max(tx_i, tx_p)
        ov_right = min(tx_i + W_i, tx_p + W_p)

        if ov_bot - ov_top < 40 or ov_right - ov_left < 40:
            continue

        # Source-frame row/col bounds for the overlap zone
        r0_i = max(0, int(round(ov_top - ty_i)))
        r1_i = min(H_i, int(round(ov_bot - ty_i)))
        c0_i = max(0, int(round(ov_left - tx_i)))
        c1_i = min(W_i, int(round(ov_right - tx_i)))

        r0_p = max(0, int(round(ov_top - ty_p)))
        r1_p = min(H_p, int(round(ov_bot - ty_p)))
        c0_p = max(0, int(round(ov_left - tx_p)))
        c1_p = min(W_p, int(round(ov_right - tx_p)))

        # Background masks for foreground-exclusion
        bm_i = bg_masks[i] if (bg_masks is not None and bg_masks[i] is not None) else None
        bm_p = (
            bg_masks[i - 1]
            if (bg_masks is not None and bg_masks[i - 1] is not None)
            else None
        )

        stripe_means_i = [[] for _ in range(3)]
        stripe_means_p = [[] for _ in range(3)]

        bh = max(10, (r1_i - r0_i) // N_BLOCKS_Y)
        bw = max(10, (c1_i - c0_i) // N_BLOCKS_X)

        for s_r in range(N_BLOCKS_Y):
            for s_c in range(N_BLOCKS_X):
                row_i = r0_i + s_r * bh
                col_i = c0_i + s_c * bw
                
                # Corresponding predecessor coords (same canvas X, Y)
                canvas_y = ty_i + row_i
                canvas_x = tx_i + col_i
                row_p = int(round(canvas_y - ty_p))
                col_p = int(round(canvas_x - tx_p))

                # Safe bounds
                row_p = max(r0_p, min(r1_p - bh, row_p))
                col_p = max(c0_p, min(c1_p - bw, col_p))
                row_i = max(r0_i, min(r1_i - bh, row_i))
                col_i = max(c0_i, min(c1_i - bw, col_i))

                slab_i = frames[i][row_i : row_i + bh, col_i : col_i + bw].astype(np.float32)
                slab_p = frames[i - 1][row_p : row_p + bh, col_p : col_p + bw].astype(np.float32)

                # Background mask for this block
                valid = np.ones(slab_i.shape[:2], dtype=bool)
                if bm_i is not None:
                    valid &= (bm_i[row_i : row_i + bh, col_i : col_i + bw] > 127)
                if bm_p is not None:
                    valid_p = bm_p[row_p : row_p + bh, col_p : col_p + bw] > 127
                    valid &= valid_p

                if valid.sum() < MIN_BG_PX:
                    valid = np.ones(slab_i.shape[:2], dtype=bool)
                    if valid.sum() < MIN_BG_PX:
                        continue

                slab_p_corr = np.clip(
                    slab_p * gains[i - 1] + biases[i - 1], 0, 255
                )

                for c in range(3):
                    mu_i = float(slab_i[valid, c].mean())
                    mu_p = float(slab_p_corr[valid, c].mean())
                    if mu_i > 5.0:
                        stripe_means_i[c].append(mu_i)
                        stripe_means_p[c].append(mu_p)

        for c in range(3):
            if len(stripe_means_i[c]) < 3:
                continue
            arr_i = np.array(stripe_means_i[c])
            arr_p = np.array(stripe_means_p[c])
            # Use median ratio across stripes → robust to outlier stripes
            ratios = arr_p / np.maximum(arr_i, 1.0)
            g = float(np.clip(np.median(ratios), 0.88, 1.12))
            b = float(np.clip(float(np.median(arr_p - arr_i * g)), -20.0, 20.0))
            gains[i, c] = g
            biases[i, c] = b

    return gains, biases


def _cluster_animation_phases(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    H: int,
    W: int,
    target_w: int = 320,
    ac_threshold: float = 0.25,
    min_anim_pixels: int = 500,
):
    """
    Detect cyclic animation pixels via per-pixel FFT along the temporal axis,
    then cluster frames by animation phase.

    Returns
    -------
    anim_mask_full : (H, W) uint8 — 255 = animation pixel — or None.
    phase_groups   : list of frame-index lists, one per phase, or None.
    """
    N = len(frames)
    if N < 4:
        return None, None

    scale = target_w / max(W, 1)
    th = max(1, int(H * scale))
    tw = target_w

    small_stack = []
    for i in range(N):
        tx = float(affines[i][0, 2])
        ty = float(affines[i][1, 2])
        M_small = np.array(
            [[scale, 0.0, tx * scale], [0.0, scale, ty * scale]], np.float32
        )
        warped = cv2.warpAffine(
            frames[i],
            M_small,
            (tw, th),
            flags=cv2.INTER_AREA,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        small_stack.append(gray)

    stack_arr = np.stack(small_stack, axis=0)  # (N, th, tw)

    # Per-pixel FFT along temporal axis
    F = np.fft.rfft(stack_arr, axis=0)
    power = np.abs(F) ** 2
    dc_power = power[0]
    ac_power = power[1:].sum(axis=0)
    ratio = ac_power / (dc_power + ac_power + 1e-8)

    anim_mask_small = (ratio > ac_threshold).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    anim_mask_small = cv2.morphologyEx(anim_mask_small, cv2.MORPH_OPEN, kernel)
    anim_mask_small = cv2.morphologyEx(anim_mask_small, cv2.MORPH_CLOSE, kernel)

    if int(anim_mask_small.sum()) // 255 < min_anim_pixels:
        return None, None

    anim_mask_full = cv2.resize(
        anim_mask_small, (W, H), interpolation=cv2.INTER_NEAREST
    )

    # Edge-signature KMeans clustering for phase assignment
    anim_ys, anim_xs = np.where(anim_mask_small > 0)
    sigs = []
    for gray in small_stack:
        edges = cv2.Canny((gray * 255).astype(np.uint8), 50, 150)
        sigs.append(edges[anim_ys, anim_xs].astype(np.float32))

    sig_matrix = np.stack(sigs, axis=0)
    n_clusters = max(2, min(8, N // 2))

    try:
        from sklearn.cluster import KMeans

        km = KMeans(n_clusters=n_clusters, n_init=5, random_state=0)
        labels = km.fit_predict(sig_matrix)
    except ImportError:
        labels = np.arange(N) % n_clusters

    phase_groups = [
        [idx for idx in range(N) if labels[idx] == k]
        for k in range(n_clusters)
        if any(labels == k)
    ]

    return anim_mask_full, phase_groups






def _render_median(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    bg_masks: List[Optional[np.ndarray]],
    H: int,
    W: int,
    _baselines: Optional[List[float]] = None,
    _skip_anim: bool = False,
    confidence_weights: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray], List[np.ndarray]]:
    """
    Memory-efficient and FAST Temporal Median Render.
    Avoids float32 conversion and nanmedian where possible.

    confidence_weights : (N,) float32 per-frame matching confidence [0, 1].
        When provided and any frame has confidence < 0.70, multi-sample pixels
        use a confidence-weighted average instead of an unweighted median.
        Frames aligned via LoFTR (conf ~0.9) outweigh Template Match frames
        (conf ~0.55), reducing blur from low-quality fallback edges (P1.3).
    """
    N = len(frames)
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    valid_mask = np.zeros((H, W), dtype=np.uint8)

    # Pre-compute sequential color corrections to eliminate frame-boundary seams.
    # Matches each frame's overlap-zone photometry to its predecessor, chained
    # from frame 0.  This implements the "histogram matching" that photometric.py
    # defers to this renderer.
    _cg, _cb = _compute_sequential_color_gains(frames, affines, bg_masks=bg_masks)
    # Only apply correction when gains are small (< 5% per-channel) — large gains
    # indicate foreground contamination and would make the seam worse.
    
    _cg_safe = np.where(np.abs(_cg - 1.0) <= MAX_SAFE_GAIN_DEV, _cg, np.ones_like(_cg))
    _cb_safe = np.where(np.abs(_cg - 1.0) <= MAX_SAFE_GAIN_DEV, _cb, np.zeros_like(_cb))
    _need_color_corr = not (
        np.allclose(_cg_safe, 1.0, atol=0.005) and np.allclose(_cb_safe, 0.0, atol=0.5)
    )
    _cg, _cb = _cg_safe, _cb_safe

    scroll_axis = _detect_scroll_axis(affines)

    # Canvas entry/exit bounds for each frame (for fade-in/out)
    _frame_ty = np.array([float(affines[i][1, 2]) for i in range(N)], dtype=np.float64)
    _frame_bot = np.array(
        [_frame_ty[i] + frames[i].shape[0] for i in range(N)], dtype=np.float64
    )
    _frame_tx = np.array([float(affines[i][0, 2]) for i in range(N)], dtype=np.float64)
    _frame_right = np.array(
        [_frame_tx[i] + frames[i].shape[1] for i in range(N)], dtype=np.float64
    )

    # Precompute geometric masks for each frame to avoid confusing black pixels with borders
    _frame_masks = [np.full(f.shape[:2], 255, dtype=np.uint8) for f in frames]

    # A5 — per-frame BACKGROUND masks (uint8, 255 = background) for fg-excluded median.
    _exclude_fg = _FG_EXCLUDE_MEDIAN and any(m is not None for m in bg_masks)
    _frame_bg_u8: List[Optional[np.ndarray]] = []
    for i in range(N):
        bm = bg_masks[i] if i < len(bg_masks) else None
        if _exclude_fg and bm is not None:
            # Normalise to frame size, 255 where background.
            bm_u8 = (bm > 127).astype(np.uint8) * 255
            if bm_u8.shape[:2] != frames[i].shape[:2]:
                bm_u8 = cv2.resize(
                    bm_u8, (frames[i].shape[1], frames[i].shape[0]),
                    interpolation=cv2.INTER_NEAREST,
                )
            _frame_bg_u8.append(bm_u8)
        else:
            _frame_bg_u8.append(None)
    if _exclude_fg:
        print("[Stitch]   A5: foreground-excluded temporal median ENABLED (clean bg plate).")

    # Determine chunk size. We want to keep stack size < 1GB
    chunk_size = max(1, min(1024, (1024 * 1024 * 1024) // (N * W * 3 + 1)))

    print(f"[Stitch]   Rendering {N} frames in chunks of {chunk_size}px height...")

    for y0 in range(0, H, chunk_size):
        y1 = min(y0 + chunk_size, H)
        ch = y1 - y0

        stack = np.zeros((N, ch, W, 3), dtype=np.uint8)
        masks = np.zeros((N, ch, W), dtype=bool)
        bg_canvas = np.zeros((N, ch, W), dtype=bool) if _exclude_fg else None

        for i in range(N):
            M_strip = affines[i].copy()
            M_strip[1, 2] -= y0
            w_strip = cv2.warpAffine(
                frames[i],
                M_strip,
                (W, ch),
                flags=cv2.INTER_LANCZOS4,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            w_mask = cv2.warpAffine(
                _frame_masks[i],
                M_strip,
                (W, ch),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            valid_px = w_mask > 0
            if _exclude_fg and _frame_bg_u8[i] is not None:
                w_bg = cv2.warpAffine(
                    _frame_bg_u8[i],
                    M_strip,
                    (W, ch),
                    flags=cv2.INTER_NEAREST,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=0,
                )
                bg_canvas[i] = (w_bg > 127) & valid_px
            elif _exclude_fg:
                # No mask for this frame → treat all valid pixels as background.
                bg_canvas[i] = valid_px
            if _baselines is not None:
                b_i = _baselines[i]
                if b_i < 0.90:
                    scale = min(1.0 / max(b_i, 0.5), 1.25)
                    w_strip = np.clip(
                        w_strip.astype(np.float32) * scale, 0, 255
                    ).astype(np.uint8)
            if _need_color_corr:
                g_i = _cg[i]
                bc_i = _cb[i]
                if not (np.allclose(g_i, 1.0, atol=0.01) and np.allclose(bc_i, 0.0, atol=1.0)):
                    w_f32 = w_strip.astype(np.float32)
                    for c in range(3):
                        w_f32[:, :, c] = np.clip(w_f32[:, :, c] * g_i[c] + bc_i[c], 0, 255)
                    w_strip = w_f32.astype(np.uint8)
                    w_strip[~valid_px] = 0
            stack[i] = w_strip
            masks[i] = valid_px

        geo_count = masks.sum(axis=0)  # geometric coverage (for valid_mask, fades)

        # A5 — effective masks for the median: prefer BACKGROUND samples; where a
        # pixel has no background sample anywhere, fall back to all valid samples.
        if _exclude_fg:
            bg_count = bg_canvas.sum(axis=0)          # (ch, W)
            use_bg = bg_count >= 1                    # pixel has ≥1 background sample
            # eff_masks[i] = bg_canvas[i] where use_bg, else masks[i]
            eff_masks = np.where(use_bg[None, :, :], bg_canvas, masks)
        else:
            eff_masks = masks

        count = eff_masks.sum(axis=0)

        # Case 1: pixels with exactly 1 sample
        m1 = count == 1
        if m1.any():
            idx1 = eff_masks[:, m1].argmax(axis=0)
            rows1, cols1 = np.where(m1)
            canvas[y0:y1][rows1, cols1] = stack[idx1, rows1, cols1]

        # Case 2: pixels with > 1 samples
        m_gt1 = count > 1
        if m_gt1.any():
            canvas_strip = canvas[y0:y1]
            s_gt1 = stack.reshape(N, -1, 3)[:, m_gt1.flatten(), :]
            masks_gt1 = eff_masks.reshape(N, -1)[:, m_gt1.flatten()]

            s_gt1_f = s_gt1.astype(np.float32)

            # P1.3 — Confidence-weighted average for low-quality edges (W3).
            # When any frame has matching confidence < 0.70 (Template Match or
            # Phase Correlation fallback), replace the pure median with a
            # weighted average so high-confidence LoFTR frames dominate.
            _use_weighted = (
                confidence_weights is not None
                and float(confidence_weights.min()) < 0.70
            )
            if _use_weighted:
                # Build weight matrix: (N, P) — zero for out-of-bounds pixels
                w_mat = np.where(
                    masks_gt1,
                    confidence_weights[:, np.newaxis],
                    0.0,
                ).astype(np.float32)
                w_sum = w_mat.sum(axis=0)  # (P,)
                safe_w = np.where(w_sum > 0, w_sum, 1.0)
                # Weighted average: (P, 3)
                med = (
                    (s_gt1_f * w_mat[:, :, np.newaxis]).sum(axis=0)
                    / safe_w[:, np.newaxis]
                )
            else:
                s_gt1_f[~masks_gt1] = np.nan
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=RuntimeWarning)
                    med = np.nanmedian(s_gt1_f, axis=0)

            canvas_strip.reshape(-1, 3)[m_gt1.flatten()] = np.clip(med, 0, 255).astype(
                np.uint8
            )

        # ── Fade-in / fade-out post-pass ────────────────────────────────────
        # For each frame whose entry or exit boundary falls inside this chunk,
        # smoothly ramp its median contribution over RENDERING_FADE_ROWS rows/cols.
        if scroll_axis != "horizontal":
            for i in range(N):
                for (fade_start, fade_end, is_entry) in [
                    (_frame_ty[i] - LANCZOS_BLEED, _frame_ty[i] + RENDERING_FADE_ROWS, True),
                    (_frame_bot[i] - RENDERING_FADE_ROWS, _frame_bot[i] + LANCZOS_BLEED, False),
                ]:
                    if fade_end <= y0 or fade_start >= y1:
                        continue  # fade zone not in this chunk

                    local_start = max(0, int(np.floor(fade_start)) - y0)
                    local_end = min(ch, int(np.ceil(fade_end)) - y0)
                    if local_start >= local_end:
                        continue

                    s_f_full = stack[:, local_start:local_end, :, :].astype(np.float32)
                    # A5: fade uses the same fg-excluded effective masks as the
                    # main median so the entry/exit ramp stays background-clean.
                    m_full = eff_masks[:, local_start:local_end, :]  # (N, rows, W)

                    s_f_no_i = s_f_full.copy()
                    m_no_i = m_full.copy()
                    m_no_i[i] = False
                    s_f_no_i[~m_no_i] = np.nan
                    s_f_full[~m_full] = np.nan

                    count_no_i = m_no_i.sum(axis=0)  # (rows, W)
                    i_present = m_full[i]              # (rows, W)
                    affected = i_present & (count_no_i >= 1)

                    if not affected.any():
                        continue

                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                        med_with = np.nanmedian(s_f_full, axis=0)     # (rows, W, 3)
                        med_without = np.nanmedian(s_f_no_i, axis=0)  # (rows, W, 3)

                    canvas_ys = np.arange(y0 + local_start, y0 + local_end, dtype=np.float64)
                    if is_entry:
                        alphas = np.clip((canvas_ys - fade_start) / RENDERING_FADE_ROWS, 0.0, 1.0)
                    else:
                        alphas = np.clip((fade_end - canvas_ys) / RENDERING_FADE_ROWS, 0.0, 1.0)
                    alphas = alphas[:, np.newaxis, np.newaxis]  # (rows, 1, 1)

                    blended = (1.0 - alphas) * med_without + alphas * med_with

                    canvas_rows = canvas[y0 + local_start : y0 + local_end]
                    aff3 = np.stack([affected] * 3, axis=-1)  # (rows, W, 3)
                    canvas_rows[aff3] = np.clip(blended[aff3], 0, 255).astype(np.uint8)
        else:
            for i in range(N):
                for (fade_start, fade_end, is_entry) in [
                    (_frame_tx[i] - LANCZOS_BLEED, _frame_tx[i] + RENDERING_FADE_ROWS, True),
                    (_frame_right[i] - RENDERING_FADE_ROWS, _frame_right[i] + LANCZOS_BLEED, False),
                ]:
                    local_start = max(0, int(np.floor(fade_start)))
                    local_end = min(W, int(np.ceil(fade_end)))
                    if local_start >= local_end:
                        continue

                    s_f_full = stack[:, :, local_start:local_end, :].astype(np.float32)
                    m_full = eff_masks[:, :, local_start:local_end]  # (N, ch, cols)

                    s_f_no_i = s_f_full.copy()
                    m_no_i = m_full.copy()
                    m_no_i[i] = False
                    s_f_no_i[~m_no_i] = np.nan
                    s_f_full[~m_full] = np.nan

                    count_no_i = m_no_i.sum(axis=0)  # (ch, cols)
                    i_present = m_full[i]              # (ch, cols)
                    affected = i_present & (count_no_i >= 1)

                    if not affected.any():
                        continue

                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                        med_with = np.nanmedian(s_f_full, axis=0)     # (ch, cols, 3)
                        med_without = np.nanmedian(s_f_no_i, axis=0)  # (ch, cols, 3)

                    canvas_xs = np.arange(local_start, local_end, dtype=np.float64)
                    if is_entry:
                        alphas = np.clip((canvas_xs - fade_start) / RENDERING_FADE_ROWS, 0.0, 1.0)
                    else:
                        alphas = np.clip((fade_end - canvas_xs) / RENDERING_FADE_ROWS, 0.0, 1.0)
                    alphas = alphas[np.newaxis, :, np.newaxis]  # (1, cols, 1)

                    blended = (1.0 - alphas) * med_without + alphas * med_with

                    canvas_cols = canvas[y0:y1, local_start:local_end]
                    aff3 = np.stack([affected] * 3, axis=-1)  # (ch, cols, 3)
                    canvas_cols[aff3] = np.clip(blended[aff3], 0, 255).astype(np.uint8)

        valid_mask[y0:y1][geo_count > 0] = 255

    if not _skip_anim and N >= 4:
        # Skip animation detection for pan shots: large vertical span means each
        # canvas pixel is covered by few frames → FFT gives spurious AC signal.
        ty_vals = [float(a[1, 2]) for a in affines]
        ty_span = max(ty_vals) - min(ty_vals)
        if ty_span > 0.25 * H:
            anim_mask, phase_groups = None, None
        else:
            anim_mask, phase_groups = _cluster_animation_phases(frames, affines, H, W)
        if anim_mask is not None and phase_groups is not None:
            print(
                f"[Stitch]   Animation detected: {len(phase_groups)} phases — re-rendering anim pixels..."
            )
            majority_group = max(phase_groups, key=len)
            sub_frames = [frames[idx] for idx in majority_group]
            sub_affines = [affines[idx] for idx in majority_group]
            sub_masks = [bg_masks[idx] for idx in majority_group]
            sub_bl = (
                [_baselines[idx] for idx in majority_group]
                if _baselines is not None
                else None
            )
            sub_cw = (
                confidence_weights[majority_group]
                if confidence_weights is not None
                else None
            )
            anim_canvas, _, _, _ = _render_median(
                sub_frames,
                sub_affines,
                sub_masks,
                H,
                W,
                _baselines=sub_bl,
                _skip_anim=True,
                confidence_weights=sub_cw,
            )
            anim_has_content = anim_canvas.max(axis=2) > 0
            overwrite_px = (anim_mask > 0) & anim_has_content
            canvas[overwrite_px] = anim_canvas[overwrite_px]

    return canvas, valid_mask, [], []


def _render_first(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    H: int,
    W: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Simple first-frame-wins renderer."""
    canvas = np.zeros((H, W, 3), np.uint8)
    mask = np.zeros((H, W), np.uint8)
    _frame_masks = [np.full(f.shape[:2], 255, dtype=np.uint8) for f in frames]
    for img, M, f_mask in reversed(list(zip(frames, affines, _frame_masks))):
        w = cv2.warpAffine(
            img,
            M,
            (W, H),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        w_mask = cv2.warpAffine(
            f_mask,
            M,
            (W, H),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        m = (w_mask > 0).astype(np.uint8) * 255
        canvas[m > 0] = w[m > 0]
        mask |= m
    return canvas, mask


def _render_laplacian(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    bg_masks: List[Optional[np.ndarray]],
    H: int,
    W: int,
) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray], List[np.ndarray]]:
    """
    Perfect Seamless Blender: Sequential Laplacian with Optimal Seams.
    """
    N = len(frames)
    warped_list = []
    mask_list = []
    for i, (img, M, bg) in enumerate(zip(frames, affines, bg_masks)):
        w = cv2.warpAffine(
            img,
            M,
            (W, H),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        warped_list.append(w)
        mask = (w.max(axis=2) > 0).astype(np.uint8) * 255
        mask_list.append(mask)

    # ── Color Matching (Sequential: each frame matched to the previous) ────
    # Chaining to the adjacent frame gives a better reference than anchoring
    # everything to frame 0, which may have very little spatial overlap with
    # frames far along the pan.
    colour_matched = [warped_list[0].astype(np.float32)]
    for i in range(1, N):
        src = warped_list[i].astype(np.float32)
        ref = colour_matched[i - 1]
        ref_m = mask_list[i - 1] > 0
        vm = mask_list[i] > 0
        overlap = vm & ref_m
        if overlap.sum() > 5000:
            out = src.copy()
            for c in range(3):
                ref_std = ref[overlap, c].std() + 1e-6
                src_std = src[overlap, c].std() + 1e-6
                ref_mean = ref[overlap, c].mean()
                src_mean = src[overlap, c].mean()

                gain = ref_std / src_std
                gain = np.clip(gain, 0.85, 1.18)

                bias = ref_mean - (src_mean * gain)
                bias = np.clip(bias, -15.0, 15.0)

                out[..., c] = np.clip(src[..., c] * gain + bias, 0, 255)
            colour_matched.append(out)
        else:
            colour_matched.append(src)

    # ── Sequential Seamless Blend (ROI-Based Distance Transform) ───────────
    canvas = colour_matched[0].copy()
    canvas_m = mask_list[0].copy()

    for i in range(1, N):
        img = colour_matched[i]
        m_i = mask_list[i]
        overlap = (canvas_m > 0) & (m_i > 0)
        if not overlap.any():
            canvas[m_i > 0] = img[m_i > 0]
            canvas_m[m_i > 0] = 255
            continue

        ys, xs = np.where(overlap)
        y0_ov, y1_ov = int(ys.min()), int(ys.max()) + 1
        x0_ov, x1_ov = int(xs.min()), int(xs.max()) + 1

        feather = 40
        y0_ov = max(0, y0_ov - feather)
        y1_ov = min(H, y1_ov + feather)
        x0_ov = max(0, x0_ov - feather)
        x1_ov = min(W, x1_ov + feather)

        H_roi = y1_ov - y0_ov
        W_roi = x1_ov - x0_ov

        canvas_roi = canvas[y0_ov:y1_ov, x0_ov:x1_ov].copy()
        img_roi = img[y0_ov:y1_ov, x0_ov:x1_ov]
        m_i_roi = m_i[y0_ov:y1_ov, x0_ov:x1_ov]
        canvas_m_roi = canvas_m[y0_ov:y1_ov, x0_ov:x1_ov]

        canvas_roi[m_i_roi > 0] = img_roi[m_i_roi > 0]
        canvas_roi[canvas_m_roi > 0] = canvas[y0_ov:y1_ov, x0_ov:x1_ov][
            canvas_m_roi > 0
        ]

        img_cross = img_roi.copy()
        img_cross[canvas_m_roi > 0] = canvas[y0_ov:y1_ov, x0_ov:x1_ov][canvas_m_roi > 0]
        img_cross[m_i_roi > 0] = img_roi[m_i_roi > 0]

        # Distance transform for soft weight map
        mask_roi = np.zeros((H_roi, W_roi), dtype=np.float32)
        mask_roi[feather : H_roi - feather, feather : W_roi - feather] = 1.0
        dist_mask = cv2.distanceTransform(
            (mask_roi * 255).astype(np.uint8), cv2.DIST_L2, 3
        )
        weight_roi = dist_mask / (dist_mask.max() + 1e-6)

        weight_roi[(m_i_roi > 0) & (canvas_m_roi == 0)] = 1.0
        weight_roi[(canvas_m_roi > 0) & (m_i_roi == 0)] = 0.0

        if bg_masks[i] is not None:
            fg_i = bg_masks[i] < 127
            w_fg_i = cv2.warpAffine(
                fg_i.astype(np.uint8) * 255,
                affines[i],
                (W, H),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            w_fg_roi = w_fg_i[y0_ov:y1_ov, x0_ov:x1_ov]
            weight_roi[w_fg_roi > 127] = 1.0

        blended_roi = _laplacian_blend(img_cross, canvas_roi, weight_roi)

        update_mask = (m_i_roi > 0) | (canvas_m_roi > 0)
        canvas[y0_ov:y1_ov, x0_ov:x1_ov][update_mask] = blended_roi[update_mask]
        canvas_m |= m_i

    warped_fgs = []
    for i, (M, bg) in enumerate(zip(affines, bg_masks)):
        if bg is not None:
            fg = (bg < 127).astype(np.uint8) * 255
            w_fg = cv2.warpAffine(
                fg,
                M,
                (W, H),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
            warped_fgs.append(w_fg)
        else:
            warped_fgs.append(np.zeros((H, W), np.uint8))

    return (
        canvas.astype(np.uint8),
        canvas_m,
        [c.astype(np.uint8) for c in colour_matched],
        warped_fgs,
    )


def _render(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    bg_masks: List[Optional[np.ndarray]],
    canvas_h: int,
    canvas_w: int,
    renderer: str = "median",
    baselines: Optional[List[float]] = None,
    confidence_weights: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray], List[np.ndarray]]:
    """Dispatcher for different rendering modes."""
    if renderer == "median":
        return _render_median(
            frames,
            affines,
            bg_masks,
            canvas_h,
            canvas_w,
            _baselines=baselines,
            confidence_weights=confidence_weights,
        )
    elif renderer == "first":
        c, v = _render_first(frames, affines, canvas_h, canvas_w)
        return c, v, [], []
    else:
        return _render_laplacian(frames, affines, bg_masks, canvas_h, canvas_w)


__all__ = [
    "_render",
    "_render_median",
    "_render_first",
    "_render_laplacian",
    "_cluster_animation_phases",
]
