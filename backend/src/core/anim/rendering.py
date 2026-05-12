"""
Temporal rendering: median, first-frame, and Laplacian-blend renderers.

All functions are standalone — they take ``frames``, ``affines`` and (where
applicable) ``bg_masks`` as explicit arguments.
"""

from __future__ import annotations

import warnings
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .stateless import _laplacian_blend


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
) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray], List[np.ndarray]]:
    """
    Memory-efficient and FAST Temporal Median Render.
    Avoids float32 conversion and nanmedian where possible.
    """
    N = len(frames)
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    valid_mask = np.zeros((H, W), dtype=np.uint8)

    # Determine chunk size. We want to keep stack size < 1GB
    chunk_size = max(1, min(1024, (1024 * 1024 * 1024) // (N * W * 3 + 1)))

    print(f"[Stitch]   Rendering {N} frames in chunks of {chunk_size}px height...")

    for y0 in range(0, H, chunk_size):
        y1 = min(y0 + chunk_size, H)
        ch = y1 - y0

        stack = np.zeros((N, ch, W, 3), dtype=np.uint8)
        masks = np.zeros((N, ch, W), dtype=bool)

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
            if _baselines is not None:
                b_i = _baselines[i]
                if b_i < 0.90:
                    scale = min(1.0 / max(b_i, 0.5), 1.25)
                    w_strip = np.clip(
                        w_strip.astype(np.float32) * scale, 0, 255
                    ).astype(np.uint8)
            stack[i] = w_strip
            masks[i] = w_strip.max(axis=2) > 0

        count = masks.sum(axis=0)

        # Case 1: pixels with exactly 1 sample
        m1 = count == 1
        if m1.any():
            idx1 = masks[:, m1].argmax(axis=0)
            canvas_strip = canvas[y0:y1]
            s_flat = stack.reshape(N, -1, 3)
            m1_flat = m1.flatten()
            canvas_strip.reshape(-1, 3)[m1_flat] = s_flat[idx1, np.arange(len(idx1))]

        # Case 2: pixels with > 1 samples
        m_gt1 = count > 1
        if m_gt1.any():
            canvas_strip = canvas[y0:y1]
            s_gt1 = stack.reshape(N, -1, 3)[:, m_gt1.flatten(), :]
            masks_gt1 = masks.reshape(N, -1)[:, m_gt1.flatten()]

            s_gt1_f = s_gt1.astype(np.float32)
            s_gt1_f[~masks_gt1] = np.nan
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)
                med = np.nanmedian(s_gt1_f, axis=0)
            canvas_strip.reshape(-1, 3)[m_gt1.flatten()] = np.clip(med, 0, 255).astype(
                np.uint8
            )

        valid_mask[y0:y1][count > 0] = 255

    if not _skip_anim and N >= 4:
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
            anim_canvas, _, _, _ = _render_median(
                sub_frames,
                sub_affines,
                sub_masks,
                H,
                W,
                _baselines=sub_bl,
                _skip_anim=True,
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
    for img, M in reversed(list(zip(frames, affines))):
        w = cv2.warpAffine(
            img,
            M,
            (W, H),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        m = (w.max(axis=2) > 0).astype(np.uint8) * 255
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

    # ── Color Matching (Mean + StdDev Anchor to Frame 0) ───────────────────
    ref_idx = 0
    ref_img = warped_list[ref_idx].astype(np.float32)
    ref_m = mask_list[ref_idx] > 0
    colour_matched = [ref_img]
    for i in range(1, N):
        src = warped_list[i].astype(np.float32)
        vm = mask_list[i] > 0
        overlap = vm & ref_m
        if overlap.sum() > 5000:
            out = src.copy()
            for c in range(3):
                ref_std = ref_img[overlap, c].std() + 1e-6
                src_std = src[overlap, c].std() + 1e-6
                ref_mean = ref_img[overlap, c].mean()
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

        blended_roi = _laplacian_blend(img_cross, canvas_roi, weight_roi, 10)

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
