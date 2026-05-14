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



_FEATHER_MAX = 200         # maximum feather half-width (low-diff boundaries)
_FEATHER_MIN = 60          # minimum target feather (before inter-boundary cap)
_GAIN_CLAMP = (0.93, 1.07) # per-boundary photometric correction limit (±7%); larger values cause banding against the scene's natural top-to-bottom brightness gradient
_SEQ_SAMPLE_HALF = 40      # rows each side of boundary used for gain estimation
_SEQ_MIN_PX = 200          # minimum pixels required for reliable gain estimation
_SEARCH_RANGE = 250        # px each side to search for optimal boundary placement
_SEARCH_SLAB = 20          # row height used when scoring candidate positions

_SEAM_RAMP_HALF = 150      # rows each side for post-composite seam colour ramp (capped by boundary spacing)
_SEAM_MEAS_SLAB = 40       # rows used to measure canvas colour just outside feather zone
_SEAM_STEP_THRESHOLD = 6.0 # min per-channel colour step (0-255) to trigger ramp correction
_SEAM_MAX_RATIO = 1.20     # max mu_top/mu_bot ratio treated as calibration error; beyond this it's scene content

# Adaptive feather: diff thresholds → target half-width.
# Wide feathers are preferred: a wide linear blend of two well-aligned frames
# is far less visible than a narrow blend.  Actual feather is then capped by
# half the inter-boundary distance so zones never overlap.
_FEATHER_TABLE = [
    (10.0, 200),
    (25.0, 120),
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
        best_diff = float("inf")   # tracks bg_diff at chosen position (for logging)
        best_score = float("inf")  # combined objective minimised during search

        bg_a = warped_bgs[fi_a]
        bg_b = warped_bgs[fi_b]

        for y_cand in range(y_lo, min(y_hi, H - _SEARCH_SLAB)):
            slab_a = warped_list[fi_a][y_cand : y_cand + _SEARCH_SLAB].astype(np.float32)
            slab_b = warped_list[fi_b][y_cand : y_cand + _SEARCH_SLAB].astype(np.float32)
            all_valid = (slab_a.max(axis=2) > 0) & (slab_b.max(axis=2) > 0)
            if all_valid.sum() < 50:
                continue

            # Total diff always computed — captures character content ghosting cost.
            all_d = float(np.abs(slab_a - slab_b).mean(axis=2)[all_valid].mean())

            # Background diff preferred when enough bg pixels are present.
            # Combined score (40% bg + 60% total) balances background stability
            # against character ghosting; pure bg_diff search ignores ghosting cost.
            bg_d = None
            if bg_a is not None and bg_b is not None:
                bg_cand = (
                    bg_a[y_cand : y_cand + _SEARCH_SLAB]
                    & bg_b[y_cand : y_cand + _SEARCH_SLAB]
                    & all_valid
                )
                if bg_cand.sum() >= 50:
                    bg_d = float(np.abs(slab_a - slab_b).mean(axis=2)[bg_cand].mean())

            score = (0.4 * bg_d + 0.6 * all_d) if bg_d is not None else all_d

            if score < best_score:
                best_score = score
                best_diff = bg_d if bg_d is not None else all_d
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
        # content differs even moderately (total_diff ≥ 20), use total_diff so
        # incompatible poses get a narrow blend zone rather than wide ghosting.
        feather_metric = best_diff if (best_diff < 20.0 and total_diff < 20.0) else total_diff

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


def _apply_canvas_seam_correction(
    canvas: np.ndarray,
    boundaries: np.ndarray,
    feathers: np.ndarray,
    order: np.ndarray,
    bg_masks: List[Optional[np.ndarray]],
    affines: List[np.ndarray],
    H: int,
    W: int,
) -> None:
    """
    Post-composite wide cosine ramp to hide remaining colour steps at boundaries.

    The bell-curve in _apply_boundary_correction concentrates its correction within
    ±feather rows of the boundary.  Outside that zone the warped frames are
    uncorrected, so visible steps remain wherever the mismatch (from any cause —
    photometric calibration or natural scene gradient at the boundary) exceeds the
    threshold.  This function smooths those steps by distributing them over a wider
    ramp, making them perceptually invisible.

    Ramp half-width is capped by half the distance to the neighbouring boundary so
    adjacent ramps never overlap.  Raw ratio must be within _SEAM_MAX_RATIO
    (otherwise the step is from scene-content transitions, not calibration).
    Gains are clamped to _GAIN_CLAMP to limit the maximum correction per channel.
    """
    n_bounds = len(boundaries)
    for k, by in enumerate(boundaries):
        by_i = int(by)
        feather = int(feathers[k])
        fi_above = int(order[k])
        fi_below = int(order[k + 1])

        # Dynamic ramp: cap at half the distance to the neighbouring boundary
        half_above = int(by_i - boundaries[k - 1]) // 2 if k > 0 else by_i
        half_below = int(boundaries[k + 1] - by_i) // 2 if k < n_bounds - 1 else H - by_i
        ramp_half = min(_SEAM_RAMP_HALF, half_above, half_below)

        # Measurement slabs: just outside the feather zone on each side
        top_y0 = max(0, by_i - feather - _SEAM_MEAS_SLAB)
        top_y1 = max(0, by_i - feather)
        bot_y0 = min(H, by_i + feather)
        bot_y1 = min(H, by_i + feather + _SEAM_MEAS_SLAB)

        if top_y1 <= top_y0 or bot_y1 <= bot_y0:
            continue

        top_slab = canvas[top_y0:top_y1].astype(np.float32)
        bot_slab = canvas[bot_y0:bot_y1].astype(np.float32)

        # Prefer foreground pixels (skin) — background dilutes the signal
        top_all_valid = top_slab.max(axis=2) > 0
        bot_all_valid = bot_slab.max(axis=2) > 0

        bm_top = _warp_bg_strip(bg_masks[fi_above], affines[fi_above], top_y0, top_y1, W)
        bm_bot = _warp_bg_strip(bg_masks[fi_below], affines[fi_below], bot_y0, bot_y1, W)

        top_valid = (~bm_top) & top_all_valid if (bm_top is not None and (~bm_top & top_all_valid).sum() >= 50) else top_all_valid
        bot_valid = (~bm_bot) & bot_all_valid if (bm_bot is not None and (~bm_bot & bot_all_valid).sum() >= 50) else bot_all_valid

        if top_valid.sum() < 50 or bot_valid.sum() < 50:
            continue

        gains = np.ones(3, dtype=np.float64)
        any_above_threshold = False
        deltas = []
        for c in range(3):
            mu_top = float(top_slab[top_valid, c].mean())
            mu_bot = float(bot_slab[bot_valid, c].mean())
            deltas.append(mu_top - mu_bot)
            if mu_top < 10.0 or mu_bot < 10.0:
                continue
            if abs(mu_top - mu_bot) < _SEAM_STEP_THRESHOLD:
                continue
            raw_ratio = mu_top / mu_bot
            if raw_ratio > _SEAM_MAX_RATIO or raw_ratio < 1.0 / _SEAM_MAX_RATIO:
                continue  # scene content transition (dark curtain→bright skin), not calibration
            gains[c] = float(np.clip(raw_ratio, _GAIN_CLAMP[0], _GAIN_CLAMP[1]))
            any_above_threshold = True

        print(
            f"[Stitch]     Seam check B{k} (y≈{by_i}, ramp=±{ramp_half}px, "
            f"fg_top={top_valid.sum()}, fg_bot={bot_valid.sum()}): "
            f"ΔB={deltas[0]:.1f} ΔG={deltas[1]:.1f} ΔR={deltas[2]:.1f}"
        )

        if not any_above_threshold:
            continue

        print(
            f"[Stitch]     Seam ramp B{k} (y≈{by_i}): "
            f"B={gains[0]:.3f} G={gains[1]:.3f} R={gains[2]:.3f}"
        )

        # Ramp above: gain lerps from 1.0 (far edge) to 1/sqrt(gains) (at seam)
        y_above_start = max(0, by_i - ramp_half)
        y_above_end = by_i
        if y_above_end > y_above_start:
            n_rows = y_above_end - y_above_start
            t = np.linspace(0.0, 1.0, n_rows, endpoint=False, dtype=np.float64)
            cosine_t = 0.5 * (1.0 - np.cos(np.pi * t))
            chunk = canvas[y_above_start:y_above_end].astype(np.float32)
            for c in range(3):
                if gains[c] == 1.0:
                    continue
                gain_at_seam = 1.0 / np.sqrt(gains[c])
                row_gains = (1.0 + (gain_at_seam - 1.0) * cosine_t).astype(np.float32)
                row_gains = np.clip(row_gains, 0.90, 1.12)
                chunk[:, :, c] = np.clip(chunk[:, :, c] * row_gains[:, np.newaxis], 0, 255)
            canvas[y_above_start:y_above_end] = chunk.astype(np.uint8)

        # Ramp below: gain from sqrt(gains) (at seam) down to 1.0
        y_below_start = by_i
        y_below_end = min(H, by_i + ramp_half)
        if y_below_end > y_below_start:
            n_rows = y_below_end - y_below_start
            t = np.linspace(0.0, 1.0, n_rows, endpoint=False, dtype=np.float64)
            cosine_t = 0.5 * (1.0 - np.cos(np.pi * t))
            chunk = canvas[y_below_start:y_below_end].astype(np.float32)
            for c in range(3):
                if gains[c] == 1.0:
                    continue
                gain_at_seam = np.sqrt(gains[c])
                row_gains = (gain_at_seam + (1.0 - gain_at_seam) * cosine_t).astype(np.float32)
                row_gains = np.clip(row_gains, 0.90, 1.12)
                chunk[:, :, c] = np.clip(chunk[:, :, c] * row_gains[:, np.newaxis], 0, 255)
            canvas[y_below_start:y_below_end] = chunk.astype(np.uint8)


def _seam_cut(img1: np.ndarray, img2: np.ndarray, edge_weight: float = 15.0) -> np.ndarray:
    """
    DP seam cut that strongly avoids outlines in *either* frame.

    Energy = diff(img1,img2) + grad(diff) + edge_weight*(edges_in_img1 + edges_in_img2)

    The per-frame edge penalty makes the seam route through flat cel-shaded
    regions (skin, background) rather than through character outlines.  Even
    when both frames show different content at the same position, a path through
    flat-colour areas will have low outline energy → nearly invisible cut.

    Returns path[x] = y-offset in [0, h-1] for the minimum-energy horizontal
    cut running left→right across the (h × W × 3) slices.
    """
    diff = cv2.absdiff(img1, img2).astype(np.float32).mean(axis=2)  # (h, W)
    gx_d = cv2.Sobel(diff, cv2.CV_32F, 1, 0, ksize=3)
    gy_d = cv2.Sobel(diff, cv2.CV_32F, 0, 1, ksize=3)
    energy = diff + 0.5 * (np.abs(gx_d) + np.abs(gy_d))

    for img in (img1, img2):
        gray = img.astype(np.float32).mean(axis=2)
        gx_i = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy_i = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        energy += edge_weight * (np.abs(gx_i) + np.abs(gy_i))

    # Transpose (h, W) → (W, h) so DP runs left→right; path[x] = y-offset
    E = energy.T.copy()  # (W, h_zone)
    W_e, h_e = E.shape
    for i in range(1, W_e):
        prev = E[i - 1]
        left = np.empty_like(prev); left[0] = np.inf; left[1:] = prev[:-1]
        right = np.empty_like(prev); right[-1] = np.inf; right[:-1] = prev[1:]
        E[i] += np.minimum(prev, np.minimum(left, right))

    path = np.zeros(W_e, np.int32)
    j = int(np.argmin(E[W_e - 1]))
    path[W_e - 1] = j
    for i in range(W_e - 2, -1, -1):
        nbrs = [j]
        if j > 0:
            nbrs.append(j - 1)
        if j < h_e - 1:
            nbrs.append(j + 1)
        j = nbrs[int(np.argmin([E[i, c] for c in nbrs]))]
        path[i] = j
    return path  # path[x] in [0, h_zone-1]


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

    # Cap each feather at half the inter-boundary gap so zones never overlap.
    # This lets narrow-strip boundaries use the widest feather they can fit.
    n_b = len(boundaries)
    for k in range(n_b):
        gap_above = int(boundaries[k]) if k == 0 else int(boundaries[k] - boundaries[k - 1])
        gap_below = (H - int(boundaries[k])) if k == n_b - 1 else int(boundaries[k + 1] - boundaries[k])
        max_feather = max(5, min(gap_above, gap_below) // 2 - 1)
        if feathers[k] > max_feather:
            feathers[k] = float(max_feather)
    print(
        "[Stitch]   Feathers (gap-capped): "
        + " ".join(f"B{k}={int(feathers[k])}px" for k in range(n_b))
    )

    # ── Flat-cut boundaries + per-seam colour correction ─────────────────────
    # DP seam paths are abandoned: in all-character zones (bg_diff=inf) the
    # energy landscape is flat so the DP wanders erratically to zone edges,
    # producing a jagged staircase pattern.  A flat horizontal cut at the
    # optimised boundary is predictable and avoids that artefact.
    #
    # Colour correction: sample mean colour from fa just above and fb just
    # below the cut.  Correct fb toward fa brightness with a linear ramp
    # (full correction at the cut, zero at the zone bottom edge).  One-sided
    # (only fb is corrected) so fa above the cut is untouched and no
    # artificial gradient is introduced there.
    SEAM_THIN_HF = 8        # ±px linear feather at the flat cut line
    SLAB_HALF = 25          # rows sampled on each side to estimate colour step
    GAIN_CLAMP_LOCAL = (0.80, 1.25)

    print("[Stitch]   Computing boundary colour corrections...")
    # (fi_above, fi_below, y0_f, y1_f, y_cut, gain_seam)
    seam_zones: List[Tuple[int, int, int, int, int, np.ndarray]] = []

    for k, by in enumerate(boundaries):
        feather = int(feathers[k])
        fi_above = int(order[k])
        fi_below = int(order[k + 1])
        y0_f = max(0, int(by) - feather)
        y1_f = min(H, int(by) + feather + 1)
        if y0_f >= y1_f:
            continue

        y_cut = int(by)

        # Measure mean colour just above and just below the flat cut
        ya0 = max(0, y_cut - SLAB_HALF)
        ya1 = y_cut
        yb0 = y_cut
        yb1 = min(H, y_cut + SLAB_HALF)

        fa_slab = warped_list[fi_above][ya0:ya1].astype(np.float32)
        fb_slab = warped_list[fi_below][yb0:yb1].astype(np.float32)
        mask_a = fa_slab.max(axis=2) > 0
        mask_b = fb_slab.max(axis=2) > 0

        if mask_a.sum() >= 50 and mask_b.sum() >= 50:
            mu_a = fa_slab[mask_a].mean(axis=0) + 1.0
            mu_b = fb_slab[mask_b].mean(axis=0) + 1.0
            gain_seam = np.clip(
                mu_a / mu_b, GAIN_CLAMP_LOCAL[0], GAIN_CLAMP_LOCAL[1]
            ).astype(np.float32)
        else:
            gain_seam = np.ones(3, dtype=np.float32)

        seam_zones.append((fi_above, fi_below, y0_f, y1_f, y_cut, gain_seam))
        print(
            f"[Stitch]     Boundary B{k} (frames {fi_above}/{fi_below}): "
            f"y_cut={y_cut} zone=[{y0_f}–{y1_f}] "
            f"gain=[{gain_seam[0]:.3f},{gain_seam[1]:.3f},{gain_seam[2]:.3f}]"
        )

    # ── Hard-partition strip_weights; zero seam zones (per-pixel below) ───────
    all_ys = np.arange(H, dtype=np.float64)
    owner_bin = np.clip(np.searchsorted(boundaries, all_ys, side="right"), 0, N - 1)
    owner = order[owner_bin]
    strip_weights = np.zeros((N, H), np.float32)
    strip_weights[owner, np.arange(H)] = 1.0
    for _fi_a, _fi_b, y0_f, y1_f, _yc, _gs in seam_zones:
        strip_weights[:, y0_f:y1_f] = 0.0

    # ── Composite ─────────────────────────────────────────────────────────────
    CHUNK = 512
    for y0 in range(0, H, CHUNK):
        y1 = min(y0 + CHUNK, H)
        ch = y1 - y0

        num = np.zeros((ch, W, 3), dtype=np.float32)
        denom = np.zeros((ch, W), dtype=np.float32)

        # Hard-partition rows (outside all seam zones)
        for i in range(N):
            fc = warped_list[i][y0:y1].astype(np.float32)
            has_content = fc.max(axis=2) > 0
            w_strip = strip_weights[i, y0:y1]
            w_eff = w_strip[:, np.newaxis] * has_content.astype(np.float32)
            num += w_eff[:, :, np.newaxis] * fc
            denom += w_eff

        # Seam-zone rows: flat-cut composite with one-sided colour correction
        for fi_above, fi_below, y0_f, y1_f, y_cut, gain_seam in seam_zones:
            iy0 = max(y0, y0_f)
            iy1 = min(y1, y1_f)
            if iy0 >= iy1:
                continue

            cy0 = iy0 - y0
            cy1 = iy1 - y0

            fa = warped_list[fi_above][iy0:iy1].astype(np.float32)  # (sub, W, 3)
            fb = warped_list[fi_below][iy0:iy1].astype(np.float32)

            local_ys = np.arange(iy0, iy1, dtype=np.float32)[:, np.newaxis]
            d = local_ys - float(y_cut)  # (sub, 1); <0 above cut, >0 below

            # Symmetric √-gain: each side ramps to the geometric mean at the cut.
            # Both fa_corr and fb_corr converge to sqrt(mu_fa*mu_fb) at y_cut,
            # producing a seamless join with shallow symmetric gradients on each side.
            zone_above_h = max(1.0, float(y_cut - y0_f))
            zone_below_h = max(1.0, float(y1_f - y_cut))
            t_above = np.clip(np.abs(np.minimum(d, 0.0)) / zone_above_h, 0.0, 1.0)
            t_below = np.clip(np.maximum(d, 0.0) / zone_below_h, 0.0, 1.0)

            sqrt_gain = np.sqrt(gain_seam).astype(np.float32)        # (3,)
            inv_sqrt_gain = (1.0 / sqrt_gain).astype(np.float32)     # (3,)

            gain_fa = 1.0 + (1.0 - t_above[:, :, np.newaxis]) * (inv_sqrt_gain - 1.0)
            gain_fb = 1.0 + (1.0 - t_below[:, :, np.newaxis]) * (sqrt_gain - 1.0)

            fa_corr = np.clip(fa * gain_fa, 0.0, 255.0)
            fb_corr = np.clip(fb * gain_fb, 0.0, 255.0)

            # Linear feather at the flat cut
            t_hf = np.clip(
                (d + SEAM_THIN_HF) / (2.0 * SEAM_THIN_HF), 0.0, 1.0
            )[:, :, np.newaxis]
            result = (1.0 - t_hf) * fa_corr + t_hf * fb_corr
            result = np.clip(result, 0.0, 255.0)

            has_a = fa.max(axis=2) > 0
            has_b = fb.max(axis=2) > 0
            has_any = (has_a | has_b).astype(np.float32)

            only_a = has_a & ~has_b
            only_b = ~has_a & has_b
            result = np.where(only_a[:, :, np.newaxis], fa_corr, result)
            result = np.where(only_b[:, :, np.newaxis], fb_corr, result)

            num[cy0:cy1] += result * has_any[:, :, np.newaxis]
            denom[cy0:cy1] += has_any

        safe_d = np.where(denom > 0, denom, 1.0)
        blended = np.clip(num / safe_d[:, :, np.newaxis], 0, 255)
        covered = (denom > 0)[:, :, np.newaxis]
        canvas[y0:y1] = np.where(
            covered, blended, canvas[y0:y1].astype(np.float32),
        ).astype(np.uint8)

    return canvas


__all__ = ["_composite_foreground"]
