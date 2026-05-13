"""
Full-frame hard-partition composite for animated vertical-scroll stitches.

Two root causes of the "ghosted characters" problem:
  1. The temporal median blends all frames → animated characters appear as blurry
     multi-pose averages across the entire canvas.
  2. Foreground-only compositing cannot fix character pixels that BiRefNet
     misclassifies as background (common for light skin against bright backgrounds).

This module fixes both by replacing the *entire* canvas — not just BiRefNet-
detected foreground — with the single best frame for each canvas row.
Ownership is determined by the nearest strip-centre (canvas_ty + frame_h/2).
A ±feather-pixel linear blend at each ownership boundary ensures smooth visual
transitions without mixing two different character poses across a wide region.

Where the owning frame has no warped content (outside its covered area), the
incoming canvas (temporal median) is kept as the fallback.

Optimal boundary placement: after warping all frames, for each pair of adjacent
frames the boundary is moved (within ±SEARCH_RANGE rows of the midpoint) to the
y-position where the two frames are most photometrically similar.  This avoids
placing boundaries across scene-content transitions caused by animation motion.

Adaptive feathering: the feather half-width is scaled down for boundaries where
the two adjacent frames are very different (high diff score), reducing the
double-exposure transition band.  Boundaries where frames are nearly identical
get the full FEATHER_MAX blend for a seamless photometric join.

Photometric correction: bell-curve gain at each boundary scales the below frame
toward the above frame's colour.  Background-pixel estimates are preferred;
all-pixel fallback is used when bg and all-pixel signals disagree in direction
(meaning the character skin is the visible seam source).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np


_FEATHER_MAX = 60          # maximum feather half-width (low-diff boundaries)
_FEATHER_MIN = 10          # minimum feather half-width (very high-diff boundaries)
_GAIN_CLAMP = (0.80, 1.20) # per-boundary photometric correction limits (±20%)
_SEQ_SAMPLE_HALF = 40      # rows each side of boundary used for gain estimation
_SEQ_MIN_PX = 200          # minimum pixels required for reliable gain estimation
_SEARCH_RANGE = 300        # px each side to search for optimal boundary placement
_SEARCH_SLAB = 20          # row height used when scoring candidate positions

# Adaptive feather: diff thresholds → feather half-width
_FEATHER_TABLE = [
    (20.0, 60),
    (28.0, 40),
    (float("inf"), _FEATHER_MIN),
]


def _diff_to_feather(diff: float) -> int:
    for threshold, feather in _FEATHER_TABLE:
        if diff <= threshold:
            return feather
    return _FEATHER_MIN


def _global_gain_normalize(
    warped_list: List[np.ndarray],
    order: np.ndarray,
    initial_boundaries: np.ndarray,
    H: int,
    W: int,
    bg_masks: Optional[List[Optional[np.ndarray]]],
    affines: Optional[List[np.ndarray]],
    lam: float = 2e3,
    _SAMPLE: int = 150,
) -> None:
    """
    Least-squares balanced gain normalisation across all frames.

    Finds per-frame log-gains α_i minimising:
        Σ_{adj pairs} w_k · (α_k − α_{k+1} − log_ratio_k)²  +  lam · Σ α_i²

    This balances corrections across all frames simultaneously so no single
    frame is over-darkened.  Gains are clamped to [0.75, 1.25].
    """
    N = len(order)
    NF = len(warped_list)

    warped_bgs: List[Optional[np.ndarray]] = [None] * NF
    if bg_masks is not None and affines is not None:
        for i in range(NF):
            if bg_masks[i] is not None:
                warped_bgs[i] = cv2.warpAffine(
                    bg_masks[i].astype(np.uint8),
                    affines[i],
                    (W, H),
                    flags=cv2.INTER_NEAREST,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=0,
                ) > 127

    log_ratios = np.zeros(N - 1, dtype=np.float64)
    pair_weights = np.zeros(N - 1, dtype=np.float64)

    for k in range(N - 1):
        fi_a = int(order[k])
        fi_b = int(order[k + 1])
        by = int(initial_boundaries[k])
        y0 = max(0, by - _SAMPLE)
        y1 = min(H, by + _SAMPLE)
        if y0 >= y1:
            continue

        sa = warped_list[fi_a][y0:y1].astype(np.float64)
        sb = warped_list[fi_b][y0:y1].astype(np.float64)
        all_v = (sa.max(axis=2) > 0) & (sb.max(axis=2) > 0)
        if all_v.sum() < 20:
            continue

        valid = all_v
        if warped_bgs[fi_a] is not None and warped_bgs[fi_b] is not None:
            bg_v = warped_bgs[fi_a][y0:y1] & warped_bgs[fi_b][y0:y1] & all_v
            if bg_v.sum() >= 50:
                valid = bg_v

        mu_a = float(sa[valid, 1].mean())  # green channel
        mu_b = float(sb[valid, 1].mean())
        if mu_a > 5.0 and mu_b > 5.0:
            log_ratios[k] = np.log(mu_a / mu_b)
            pair_weights[k] = float(valid.sum())

    # Build least-squares system (N-1 pair equations + N regularisation)
    n_rows = (N - 1) + N
    A = np.zeros((n_rows, N), dtype=np.float64)
    b_vec = np.zeros(n_rows, dtype=np.float64)

    for k in range(N - 1):
        w = np.sqrt(pair_weights[k])
        A[k, k] = w
        A[k, k + 1] = -w
        b_vec[k] = w * log_ratios[k]

    for i in range(N):
        A[(N - 1) + i, i] = np.sqrt(lam)

    alpha, _, _, _ = np.linalg.lstsq(A, b_vec, rcond=None)
    gains_ord = np.clip(np.exp(alpha), 0.75, 1.25)

    gains = np.ones(NF, dtype=np.float64)
    for k, fi in enumerate(order):
        gains[fi] = float(gains_ord[k])

    print(
        "[Stitch]   LS gains: "
        + " ".join(f"F{int(order[k])}={gains_ord[k]:.3f}" for k in range(N))
    )

    for fi in range(NF):
        g = gains[fi]
        if abs(g - 1.0) < 0.005:
            continue
        frame_f = warped_list[fi].astype(np.float32)
        has_px = frame_f.max(axis=2) > 0
        frame_f[has_px] = np.clip(frame_f[has_px] * g, 0, 255)
        frame_f[~has_px] = 0.0
        warped_list[fi] = frame_f.astype(np.uint8)


def _apply_strip_gradient(
    warped_list: List[np.ndarray],
    order: np.ndarray,
    boundaries: np.ndarray,
    H: int,
    W: int,
    bg_masks: Optional[List[Optional[np.ndarray]]],
    affines: Optional[List[np.ndarray]],
    _SAMPLE: int = 60,
) -> None:
    """
    Apply a per-row gain gradient within each frame's ownership strip so that
    at the top boundary the strip photometrically matches the frame above, and
    at the bottom boundary it matches the frame below.

    For frame fi with ownership rows [y_top, y_bot]:
      gain_top  = mu(fi_above) / mu(fi)  measured at the top boundary slab
      gain_bot  = mu(fi_below) / mu(fi)  measured at the bottom boundary slab
      gain(y)   = lerp(gain_top, gain_bot, t)   t = (y − y_top) / (y_bot − y_top)

    This eliminates strip-level brightness banding without cascading errors or
    global exposure distortion.  Each strip independently ramps its own gain
    to be compatible with both neighbours at the seam locations.
    Gains are clamped per-channel to [0.67, 1.50] (±~40 %).
    """
    N = len(order)
    NF = len(warped_list)

    warped_bgs: List[Optional[np.ndarray]] = [None] * NF
    if bg_masks is not None and affines is not None:
        for i in range(NF):
            if bg_masks[i] is not None:
                warped_bgs[i] = cv2.warpAffine(
                    bg_masks[i].astype(np.uint8),
                    affines[i],
                    (W, H),
                    flags=cv2.INTER_NEAREST,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=0,
                ) > 127

    def _measure_gain(fi_ref: int, fi_tgt: int, y_center: int) -> np.ndarray:
        """Per-channel gains to scale fi_tgt to match fi_ref near y_center."""
        y0 = max(0, y_center - _SAMPLE)
        y1 = min(H, y_center + _SAMPLE)
        sr = warped_list[fi_ref][y0:y1].astype(np.float32)
        st = warped_list[fi_tgt][y0:y1].astype(np.float32)
        all_v = (sr.max(axis=2) > 0) & (st.max(axis=2) > 0)
        if all_v.sum() < 20:
            return np.ones(3, dtype=np.float32)
        valid = all_v
        if warped_bgs[fi_ref] is not None and warped_bgs[fi_tgt] is not None:
            bg_v = warped_bgs[fi_ref][y0:y1] & warped_bgs[fi_tgt][y0:y1] & all_v
            if bg_v.sum() >= 30:
                valid = bg_v
        g = np.ones(3, dtype=np.float32)
        for c in range(3):
            mu_r = float(sr[valid, c].mean())
            mu_t = float(st[valid, c].mean())
            if mu_r > 5.0 and mu_t > 5.0:
                g[c] = float(np.clip(mu_r / mu_t, 0.67, 1.50))
        return g

    for k in range(N):
        fi = int(order[k])
        y_top = 0 if k == 0 else int(boundaries[k - 1])
        y_bot = H if k == N - 1 else int(boundaries[k])
        h_strip = y_bot - y_top
        if h_strip <= 0:
            continue

        gains_top = (
            _measure_gain(int(order[k - 1]), fi, y_top) if k > 0
            else np.ones(3, dtype=np.float32)
        )
        gains_bot = (
            _measure_gain(int(order[k + 1]), fi, y_bot) if k < N - 1
            else np.ones(3, dtype=np.float32)
        )

        if np.allclose(gains_top, 1.0, atol=0.008) and np.allclose(gains_bot, 1.0, atol=0.008):
            continue

        strip = warped_list[fi][y_top:y_bot].astype(np.float32)
        has_px = strip.max(axis=2) > 0
        t = np.linspace(0.0, 1.0, h_strip, dtype=np.float32)

        for c in range(3):
            row_gain = (1.0 - t) * gains_top[c] + t * gains_bot[c]
            strip[:, :, c] *= row_gain[:, np.newaxis]

        strip[~has_px] = 0.0
        warped_list[fi][y_top:y_bot] = np.clip(strip, 0, 255).astype(np.uint8)

        print(
            f"[Stitch]     Strip F{fi} [{y_top}–{y_bot}]: "
            f"G gain {gains_top[1]:.3f}→{gains_bot[1]:.3f}"
        )


def _warp_bg_strip(
    bm: Optional[np.ndarray],
    affine: np.ndarray,
    y0: int,
    y1: int,
    W: int,
) -> Optional[np.ndarray]:
    """Warp a bg_mask slice to canvas space for rows [y0, y1) → (y1-y0, W) bool."""
    if bm is None:
        return None
    M = affine.copy()
    M[1, 2] -= y0
    strip = cv2.warpAffine(
        bm.astype(np.uint8),
        M,
        (W, y1 - y0),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return strip > 127


def _find_optimal_boundaries(
    warped_list: List[np.ndarray],
    order: np.ndarray,
    initial_boundaries: np.ndarray,
    H: int,
    W: int,
    bg_masks: Optional[List[Optional[np.ndarray]]] = None,
    affines: Optional[List[np.ndarray]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Move each boundary to the y-position (within ±SEARCH_RANGE of the midpoint)
    where the two adjacent warped frames are most photometrically similar.

    When bg_masks and affines are provided, the similarity score is computed over
    background pixels only (where both frames agree they are background).  This
    ensures the boundary is placed where the static background joins cleanly,
    which is more perceptually important than minimising character differences.
    Falls back to all-pixel diff when background pixel count is insufficient.

    Boundaries are searched left-to-right; each boundary is constrained to be
    at least 2×FEATHER_MAX from the previously placed boundary so feather zones
    never overlap even in the worst case.

    Returns (optimised_boundaries, diff_scores), both shape (N-1,).
    """
    len(order)
    optimised = initial_boundaries.copy()
    diffs = np.full(len(initial_boundaries), float("inf"))

    # Pre-warp bg_masks to canvas space so we can slice during search
    warped_bgs: List[Optional[np.ndarray]] = [None] * (max(order) + 1)
    if bg_masks is not None and affines is not None:
        for i in range(len(order)):
            fi = int(order[i])
            if bg_masks[fi] is not None:
                warped_bgs[fi] = cv2.warpAffine(
                    bg_masks[fi].astype(np.uint8),
                    affines[fi],
                    (W, H),
                    flags=cv2.INTER_NEAREST,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=0,
                ) > 127

    for k, by in enumerate(initial_boundaries):
        fi_a = int(order[k])
        fi_b = int(order[k + 1])

        # Allowed search window — 2×FEATHER_MAX separation guarantees no overlap
        lo_limit = int(optimised[k - 1]) + 2 * _FEATHER_MAX + 1 if k > 0 else _FEATHER_MAX
        hi_limit = (
            int(initial_boundaries[k + 1]) - 2 * _FEATHER_MAX - 1
            if k < len(initial_boundaries) - 1
            else H - _FEATHER_MAX - _SEARCH_SLAB
        )

        y_lo = max(lo_limit, int(by) - _SEARCH_RANGE)
        y_hi = min(hi_limit, int(by) + _SEARCH_RANGE)

        best_y = int(by)
        best_diff = float("inf")

        bg_a = warped_bgs[fi_a]
        bg_b = warped_bgs[fi_b]

        for y_cand in range(y_lo, min(y_hi, H - _SEARCH_SLAB)):
            slab_a = warped_list[fi_a][y_cand : y_cand + _SEARCH_SLAB].astype(np.float32)
            slab_b = warped_list[fi_b][y_cand : y_cand + _SEARCH_SLAB].astype(np.float32)
            all_valid = (slab_a.max(axis=2) > 0) & (slab_b.max(axis=2) > 0)
            if all_valid.sum() < 50:
                continue

            # Prefer background pixels — the seam across static background is
            # the most visually important.  Fall back to all pixels if too few bg.
            valid = all_valid
            if bg_a is not None and bg_b is not None:
                bg_valid = (
                    bg_a[y_cand : y_cand + _SEARCH_SLAB]
                    & bg_b[y_cand : y_cand + _SEARCH_SLAB]
                    & all_valid
                )
                if bg_valid.sum() >= 50:
                    valid = bg_valid

            if valid.sum() < 50:
                continue
            diff = float(np.abs(slab_a - slab_b).mean(axis=2)[valid].mean())
            if diff < best_diff:
                best_diff = diff
                best_y = y_cand + _SEARCH_SLAB // 2

        # Feather sizing: when the background matches very well (bg_diff < 10)
        # trust it for feather sizing — a wide feather gives a smooth background
        # join even if character content differs.  When background is less well
        # matched, use the total pixel diff (including character) so that a wide
        # feather doesn't create a double-exposure band across very different poses.
        half = _SEARCH_SLAB // 2
        y0_f = max(0, best_y - half)
        y1_f = min(H - 1, best_y + half)
        sa = warped_list[fi_a][y0_f:y1_f].astype(np.float32)
        sb = warped_list[fi_b][y0_f:y1_f].astype(np.float32)
        av = (sa.max(axis=2) > 0) & (sb.max(axis=2) > 0)
        total_diff = float(np.abs(sa - sb).mean(axis=2)[av].mean()) if av.sum() >= 10 else best_diff
        # Wide feather only when BOTH bg and total diffs are low; if character
        # content is very different (total_diff ≥ 40), use total_diff to avoid
        # a wide double-exposure blending band across incompatible poses.
        feather_metric = best_diff if (best_diff < 20.0 and total_diff < 40.0) else total_diff

        optimised[k] = float(best_y)
        diffs[k] = feather_metric   # store feather metric so caller uses same value
        feather = _diff_to_feather(feather_metric)
        moved = best_y - int(by)
        print(
            f"[Stitch]     Boundary {k} (frames {fi_a}/{fi_b}): "
            f"{int(by)} → {best_y} (Δ={moved:+d}, bg_diff={best_diff:.1f}, "
            f"total_diff={total_diff:.1f}, feather={feather}px)"
        )

    return optimised, diffs


def _compute_boundary_gains(
    warped_list: List[np.ndarray],
    order: np.ndarray,
    boundaries: np.ndarray,
    feathers: np.ndarray,
    bg_masks: List[Optional[np.ndarray]],
    affines: List[np.ndarray],
    H: int,
    W: int,
) -> np.ndarray:
    """
    Compute per-channel gain at each boundary.

    Samples colour in a ±SEQ_SAMPLE_HALF slab around the boundary centre.
    gain[c] = mu_above[c] / mu_below[c] — scale below frame to match above.

    bg/all direction-check: when both agree → bg (stable); disagree → all-pixel.
    Returns gains of shape (N-1, 3), dtype float32.
    """
    num_boundaries = len(boundaries)
    gains = np.ones((num_boundaries, 3), dtype=np.float32)

    for k, by in enumerate(boundaries):
        fi_above = int(order[k])
        fi_below = int(order[k + 1])

        y0 = max(0, int(by) - _SEQ_SAMPLE_HALF)
        y1 = min(H, int(by) + _SEQ_SAMPLE_HALF)
        if y0 >= y1:
            continue

        slab_a = warped_list[fi_above][y0:y1].astype(np.float64)
        slab_b = warped_list[fi_below][y0:y1].astype(np.float64)
        has_a = slab_a.max(axis=2) > 0
        has_b = slab_b.max(axis=2) > 0
        all_valid = has_a & has_b

        if all_valid.sum() < 30:
            continue

        bm_a = _warp_bg_strip(bg_masks[fi_above], affines[fi_above], y0, y1, W)
        bm_b = _warp_bg_strip(bg_masks[fi_below], affines[fi_below], y0, y1, W)
        bg_valid = None
        if bm_a is not None and bm_b is not None:
            bg_candidate = bm_a & bm_b & all_valid
            if bg_candidate.sum() >= _SEQ_MIN_PX:
                bg_valid = bg_candidate

        for c in range(3):
            mu_a_all = float(slab_a[all_valid, c].mean())
            mu_b_all = float(slab_b[all_valid, c].mean())
            if mu_a_all <= 5.0 or mu_b_all <= 5.0:
                continue
            all_ratio = mu_a_all / mu_b_all

            if bg_valid is not None:
                mu_a_bg = float(slab_a[bg_valid, c].mean())
                mu_b_bg = float(slab_b[bg_valid, c].mean())
                if mu_a_bg > 5.0 and mu_b_bg > 5.0:
                    bg_ratio = mu_a_bg / mu_b_bg
                    # agree → bg (stable); disagree → all-pixel (character is the seam)
                    chosen = bg_ratio if (bg_ratio - 1.0) * (all_ratio - 1.0) >= 0 else all_ratio
                    gains[k, c] = float(np.clip(chosen, _GAIN_CLAMP[0], _GAIN_CLAMP[1]))
                    continue

            gains[k, c] = float(np.clip(all_ratio, _GAIN_CLAMP[0], _GAIN_CLAMP[1]))

    return gains


def _apply_boundary_correction(
    warped_list: List[np.ndarray],
    order: np.ndarray,
    boundaries: np.ndarray,
    feathers: np.ndarray,
    boundary_gains: np.ndarray,
    H: int,
    W: int,
) -> None:
    """
    Apply split bell-curve gain corrections at each boundary.

    boundary_gains[k] = mu_above / mu_below.  Correcting only the below frame
    creates an asymmetric step.  Instead we split the correction symmetrically:
      gain_below[c] = sqrt(boundary_gains[k, c])          (darken below)
      gain_above[c] = 1 / sqrt(boundary_gains[k, c])      (brighten above)
    Both frames then converge to the geometric mean at the boundary centre,
    eliminating the visible step regardless of feather width.

    effective_gain(y) = 1 + (gain - 1) * 4*t*(1-t)
    t = clamp((y - by + feather) / (2*feather), 0, 1)

    Zero at feather edges, peak at boundary centre.  Modifies warped_list in-place.
    """
    def _apply_bell(fi: int, g_split: np.ndarray, by: float, feather: int) -> None:
        y0_f = max(0, int(by) - feather)
        y1_f = min(H, int(by) + feather + 1)
        if y0_f >= y1_f:
            return
        rows = np.arange(y0_f, y1_f, dtype=np.float64)
        t = np.clip((rows - by + feather) / (2.0 * feather), 0.0, 1.0)
        bell = (4.0 * t * (1.0 - t)).astype(np.float32)
        strip = warped_list[fi][y0_f:y1_f].astype(np.float32)
        has_px = strip.max(axis=2) > 0
        for c in range(3):
            if abs(g_split[c] - 1.0) < 0.003:
                continue
            strip[:, :, c] *= (1.0 + (g_split[c] - 1.0) * bell)[:, np.newaxis]
        strip[~has_px] = 0.0
        warped_list[fi][y0_f:y1_f] = np.clip(strip, 0, 255).astype(np.uint8)

    for k, by in enumerate(boundaries):
        g = boundary_gains[k]
        if np.allclose(g, 1.0, atol=0.003):
            continue

        feather = int(feathers[k])
        fi_above = int(order[k])
        fi_below = int(order[k + 1])

        # Split: each frame corrects by sqrt of the ratio toward geometric mean
        g_below = np.sqrt(np.clip(g, 1e-6, None)).astype(np.float32)
        g_above = (1.0 / np.sqrt(np.clip(g, 1e-6, None))).astype(np.float32)

        _apply_bell(fi_below, g_below, by, feather)
        _apply_bell(fi_above, g_above, by, feather)

        print(
            f"[Stitch]     Boundary {k} (y≈{int(by)}, feather={feather}px): "
            f"G g_above={g_above[1]:+.3f} g_below={g_below[1]:+.3f} "
            f"(F{fi_above}↑ / F{fi_below}↓)"
        )


def _composite_foreground(
    warped_corr: List[np.ndarray],
    warped_fgs: List[np.ndarray],
    canvas: np.ndarray,
    H: int,
    W: int,
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    bg_masks: List[Optional[np.ndarray]],
) -> np.ndarray:
    """
    Replace the temporal-median canvas with a hard-partition single-frame
    composite.  For each canvas row y the frame whose strip-centre is nearest
    supplies all pixels.  Only at the feather-pixel transition zone around each
    ownership boundary are two adjacent frames blended linearly.

    Boundaries are first optimised to the most photometrically similar y-position
    within ±SEARCH_RANGE of the midpoint.  The feather width at each boundary
    is then set adaptively based on the frame-difference score: low-diff
    boundaries get FEATHER_MAX for a smooth join; high-diff boundaries get a
    narrow feather to minimise the double-exposure transition band.

    Photometric correction via bell-curve gain is then applied at each boundary.
    """
    N = len(frames)
    print("[Stitch]   Full-frame hard-partition composite (deghost)...")

    # ── Strip centres and initial partition boundaries ────────────────────────
    strip_center_ys = np.array(
        [float(affines[i][1, 2]) + frames[i].shape[0] / 2.0 for i in range(N)],
        dtype=np.float64,
    )
    order = np.argsort(strip_center_ys)
    sorted_centers = strip_center_ys[order]
    initial_boundaries = (sorted_centers[:-1] + sorted_centers[1:]) / 2.0

    # ── Warp every frame to the full canvas ───────────────────────────────────
    warped_list: List[np.ndarray] = []
    for i in range(N):
        wf = cv2.warpAffine(
            frames[i],
            affines[i],
            (W, H),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        warped_list.append(wf)

    # ── Optimal boundary placement + adaptive feathering ─────────────────────
    print("[Stitch]   Optimising boundary placement (bg-guided)...")
    boundaries, diff_scores = _find_optimal_boundaries(
        warped_list, order, initial_boundaries, H, W,
        bg_masks=bg_masks, affines=affines,
    )
    feathers = np.array([_diff_to_feather(d) for d in diff_scores], dtype=np.float64)

    # ── Build strip_weights: hard partition + per-boundary adaptive feather ───
    all_ys = np.arange(H, dtype=np.float64)
    owner_bin = np.clip(np.searchsorted(boundaries, all_ys, side="right"), 0, N - 1)
    owner = order[owner_bin]
    strip_weights = np.zeros((N, H), np.float32)
    strip_weights[owner, np.arange(H)] = 1.0

    for k, by in enumerate(boundaries):
        feather = int(feathers[k])
        y0_f = max(0, int(by) - feather)
        y1_f = min(H, int(by) + feather + 1)
        if y0_f >= y1_f:
            continue
        rows = np.arange(y0_f, y1_f, dtype=np.float64)
        t = np.clip((rows - by + feather) / (2.0 * feather), 0.0, 1.0).astype(np.float32)
        fi_above = order[k]
        fi_below = order[k + 1]
        strip_weights[:, y0_f:y1_f] = 0.0
        strip_weights[fi_above, y0_f:y1_f] = 1.0 - t
        strip_weights[fi_below, y0_f:y1_f] = t

    # ── Photometric correction: bell-curve gain at each boundary ─────────────
    print("[Stitch]   Computing boundary photometric corrections...")
    boundary_gains = _compute_boundary_gains(
        warped_list, order, boundaries, feathers, bg_masks, affines, H, W
    )
    _apply_boundary_correction(warped_list, order, boundaries, feathers, boundary_gains, H, W)

    # ── Composite: weighted blend of owning frame(s) per chunk ───────────────
    CHUNK = 512
    for y0 in range(0, H, CHUNK):
        y1 = min(y0 + CHUNK, H)
        ch = y1 - y0

        num = np.zeros((ch, W, 3), dtype=np.float32)
        denom = np.zeros((ch, W), dtype=np.float32)

        for i in range(N):
            fc = warped_list[i][y0:y1].astype(np.float32)
            has_content = fc.max(axis=2) > 0
            w_strip = strip_weights[i, y0:y1]
            w_eff = w_strip[:, np.newaxis] * has_content.astype(np.float32)
            num += w_eff[:, :, np.newaxis] * fc
            denom += w_eff

        safe_d = np.where(denom > 0, denom, 1.0)
        blended = np.clip(num / safe_d[:, :, np.newaxis], 0, 255)

        covered = (denom > 0)[:, :, np.newaxis]
        canvas[y0:y1] = np.where(
            covered,
            blended,
            canvas[y0:y1].astype(np.float32),
        ).astype(np.uint8)

    return canvas


__all__ = ["_composite_foreground"]
