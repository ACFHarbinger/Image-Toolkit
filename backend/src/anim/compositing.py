"""
Laplacian-pyramid composite for animated vertical-scroll stitches.

For each canvas row the frame whose strip-centre is nearest supplies all
pixels (hard partition).  At ownership boundaries a Laplacian pyramid blend
routes the seam through flat cel-shaded regions via a DP energy path.
No photometric gain corrections are applied — the temporal median (Stage 9)
already ghost-removes frames and the pyramid blend is immune to the
brightness-banding artefacts produced by the earlier per-boundary LS gain
machinery.

Optimal boundary placement: for each adjacent frame pair the boundary is
moved (within ±SEARCH_RANGE rows of the midpoint) to the y-position where the
two warped frames are most photometrically similar, guided by background pixels
when available.

Adaptive feathering: the Laplacian blend half-width is scaled from the
photometric similarity score at the boundary, then capped by the natural
overlap between the two adjacent frames.
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

import cv2
import numpy as np

from backend.src.constants import (
    FEATHER_MAX,
    FEATHER_MIN,
    SEARCH_RANGE,
    SEARCH_SLAB,
    FEATHER_TABLE,
    LUMINANCE_WEIGHTS,
)

# Stage 8.5 foreground pose registration toggle (see fg_register.py).
# Enabled by default; set ASP_FG_REGISTER=0 to disable for A/B comparison.
_FG_REGISTER_ENABLED = os.environ.get("ASP_FG_REGISTER", "1") != "0"


def _diff_to_feather(diff: float) -> int:
    for threshold, feather in FEATHER_TABLE:
        if diff <= threshold:
            return feather
    return FEATHER_MIN


def _normalize_warped_to_median(
    warped: np.ndarray,
    canvas: np.ndarray,
    is_bg: Optional[np.ndarray],
    clip_lo: float = 0.75,
    clip_hi: float = 1.35,
) -> np.ndarray:
    """
    Scale warped to match canvas (temporal median) brightness at background pixels.

    Gain is computed per-channel over background pixels that are well-lit in
    both arrays, then clamped to [clip_lo, clip_hi].  This removes per-frame
    exposure offsets so adjacent ownership zones end up on the same brightness
    scale, eliminating foreground colour steps at seam boundaries.

    Returns a new uint8 array; falls back to warped unchanged when there are
    too few reliable background pixels to compute a trustworthy gain.
    """
    if is_bg is None:
        return warped

    bg_mask = is_bg & (warped.max(axis=2) > 10) & (canvas.max(axis=2) > 10)
    if int(bg_mask.sum()) < 200:
        return warped

    frame_mean = warped[bg_mask].astype(np.float32).mean(axis=0)  # (3,)
    ref_mean = canvas[bg_mask].astype(np.float32).mean(axis=0)  # (3,)

    gain = np.clip(ref_mean / np.maximum(frame_mean, 1.0), clip_lo, clip_hi)
    return np.clip(warped.astype(np.float32) * gain, 0, 255).astype(np.uint8)


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

    When bg_masks and affines are provided the score is computed over background
    pixels (static, unaffected by character pose).  Falls back to all-pixel diff
    when background pixel count is insufficient.

    Returns (optimised_boundaries, diff_scores), both shape (N-1,).
    """
    len(order)
    optimised = initial_boundaries.copy()
    diffs = np.full(len(initial_boundaries), float("inf"))

    warped_bgs: List[Optional[np.ndarray]] = [None] * (max(order) + 1)
    if bg_masks is not None and affines is not None:
        for i in range(len(order)):
            fi = int(order[i])
            if bg_masks[fi] is not None:
                warped_bgs[fi] = (
                    cv2.warpAffine(
                        bg_masks[fi].astype(np.uint8),
                        affines[fi],
                        (W, H),
                        flags=cv2.INTER_NEAREST,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=0,
                    )
                    > 127
                )

    for k, by in enumerate(initial_boundaries):
        fi_a = int(order[k])
        fi_b = int(order[k + 1])

        lo_limit = int(optimised[k - 1]) + 2 * SEARCH_SLAB + 1 if k > 0 else SEARCH_SLAB
        hi_limit = (
            int(initial_boundaries[k + 1]) - 2 * SEARCH_SLAB - 1
            if k < len(initial_boundaries) - 1
            else H - SEARCH_SLAB - SEARCH_SLAB
        )

        y_lo = max(lo_limit, int(by) - SEARCH_RANGE)
        y_hi = min(hi_limit, int(by) + SEARCH_RANGE)

        best_y = int(by)
        best_diff = float("inf")
        best_score = float("inf")

        bg_a = warped_bgs[fi_a]
        bg_b = warped_bgs[fi_b]

        for y_cand in range(y_lo, min(y_hi, H - SEARCH_SLAB)):
            slab_a = warped_list[fi_a][y_cand : y_cand + SEARCH_SLAB].astype(np.float32)
            slab_b = warped_list[fi_b][y_cand : y_cand + SEARCH_SLAB].astype(np.float32)
            all_valid = (slab_a.max(axis=2) > 0) & (slab_b.max(axis=2) > 0)
            if all_valid.sum() < 50:
                continue

            all_d = float(np.abs(slab_a - slab_b).mean(axis=2)[all_valid].mean())

            bg_d = None
            if bg_a is not None and bg_b is not None:
                bg_cand = (
                    bg_a[y_cand : y_cand + SEARCH_SLAB]
                    & bg_b[y_cand : y_cand + SEARCH_SLAB]
                    & all_valid
                )
                if bg_cand.sum() >= 50:
                    bg_d = float(np.abs(slab_a - slab_b).mean(axis=2)[bg_cand].mean())

            score = (0.4 * bg_d + 0.6 * all_d) if bg_d is not None else all_d

            if score < best_score:
                best_score = score
                best_diff = bg_d if bg_d is not None else all_d
                best_y = y_cand + SEARCH_SLAB // 2

        half = SEARCH_SLAB // 2
        y0_f = max(0, best_y - half)
        y1_f = min(H - 1, best_y + half)
        sa = warped_list[fi_a][y0_f:y1_f].astype(np.float32)
        sb = warped_list[fi_b][y0_f:y1_f].astype(np.float32)
        av = (sa.max(axis=2) > 0) & (sb.max(axis=2) > 0)
        total_diff = (
            float(np.abs(sa - sb).mean(axis=2)[av].mean())
            if av.sum() >= 10
            else best_diff
        )
        feather_metric = (
            best_diff if (best_diff < 20.0 and total_diff < 20.0) else total_diff
        )

        optimised[k] = float(best_y)
        diffs[k] = feather_metric
        feather = _diff_to_feather(feather_metric)
        moved = best_y - int(by)
        print(
            f"[Stitch]     Boundary {k} (frames {fi_a}/{fi_b}): "
            f"{int(by)} → {best_y} (Δ={moved:+d}, bg_diff={best_diff:.1f}, "
            f"total_diff={total_diff:.1f}, feather={feather}px)"
        )

    return optimised, diffs


def _seam_cut(
    img1: np.ndarray,
    img2: np.ndarray,
    edge_weight: float = 15.0,
    sem_cost: Optional[np.ndarray] = None,
    sem_weight: float = 200.0,
) -> np.ndarray:
    """
    DP seam cut that strongly avoids outlines in *either* frame.

    Energy = diff(img1,img2) + grad(diff) + edge_weight*(edges_in_img1 + edges_in_img2)
             + sem_weight * sem_cost   (P2.4 — character boundary avoidance)

    Returns path[x] = y-offset in [0, h-1] for the minimum-energy horizontal
    cut running left→right across the (h × W × 3) slices.
    """
    diff = cv2.absdiff(img1, img2).astype(np.float32).mean(axis=2)
    gx_d = cv2.Sobel(diff, cv2.CV_32F, 1, 0, ksize=3)
    gy_d = cv2.Sobel(diff, cv2.CV_32F, 0, 1, ksize=3)
    energy = diff + 0.5 * (np.abs(gx_d) + np.abs(gy_d))

    for img in (img1, img2):
        gray = img.astype(np.float32).mean(axis=2)
        gx_i = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy_i = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        energy += edge_weight * (np.abs(gx_i) + np.abs(gy_i))

    # P2.4 — Semantic character boundary avoidance
    if sem_cost is not None and sem_cost.shape == energy.shape:
        energy += sem_weight * sem_cost

    # Transpose (h, W) → (W, h) so DP runs left→right; path[x] = y-offset
    E = energy.T.copy()
    W_e, h_e = E.shape
    for i in range(1, W_e):
        prev = E[i - 1]
        left = np.empty_like(prev)
        left[0] = np.inf
        left[1:] = prev[:-1]
        right = np.empty_like(prev)
        right[-1] = np.inf
        right[:-1] = prev[1:]
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
    return path  # path[x] in [0, zone_h-1]


def _soft_seam_weight(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
    path_local: np.ndarray,
    zone_h: int,
    W: int,
    sigma: float = 15.0,
    diffuse_sigma: float = 20.0,
    bg_mask_a: Optional[np.ndarray] = None,
    bg_mask_b: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    P2.5 — Spatially-adaptive seam blend weight (DSFN technique).

    Returns (zone_h, W) float32 weight in [0, 1]:
      1.0 → fa_zone,  0.0 → fb_zone.

    Background pixels (both frames agree it's background) get a wide, smooth
    blend transition.  Foreground pixels (character) get a narrow 2-px cut so
    that after FG pose registration the blend does not smear the two slightly
    different character poses into a doubled edge.
    """
    # Per-pixel L1 distance, mean over channels → (zone_h, W)
    diff = np.abs(fa_zone.astype(np.float32) - fb_zone.astype(np.float32)).mean(axis=2)
    # Similarity field: 1 where frames agree, 0 where they differ strongly
    similarity = np.exp(-diff / max(sigma, 1.0))
    # Anisotropic diffusion: Gaussian blur propagates similarity from flat areas
    sim_diffused = cv2.GaussianBlur(
        similarity, (0, 0), sigmaX=diffuse_sigma, sigmaY=diffuse_sigma
    )
    # Blend radius per column (pixels): more similar → wider blend zone
    # Background: ramp ∈ [10, zone_h * 0.35]
    # Foreground: ramp = 2 px (tight cut — prevents character-edge doubling)
    min_ramp_bg = 10.0
    max_ramp_bg = max(min_ramp_bg + 1.0, zone_h * 0.35)
    col_sim = sim_diffused.mean(axis=0)  # (W,)
    ramp_per_col = (min_ramp_bg + col_sim * (max_ramp_bg - min_ramp_bg)).astype(np.float32)

    ys = np.arange(zone_h, dtype=np.float32)[:, np.newaxis]  # (zone_h, 1)
    seam_y = path_local[np.newaxis, :].astype(np.float32)  # (1, W)
    dist = ys - seam_y  # (zone_h, W)
    ramp = ramp_per_col[np.newaxis, :]  # (1, W)
    weight = np.clip(0.5 - dist / (2.0 * ramp), 0.0, 1.0).astype(np.float32)

    # bg_mask_a/b: True = background, False = foreground.
    # No tighter ramp for fg — after FG pose registration brings poses close,
    # the wide background-derived blend also works acceptably for fg pixels.
    # A tighter cut at character silhouettes can create its own hard seam.

    return weight


def _build_seam_cost_map(
    canvas_zone: np.ndarray,
    bg_mask_a: Optional[np.ndarray],
    bg_mask_b: Optional[np.ndarray],
    dilate_px: int = 15,
) -> np.ndarray:
    """
    P2.4 — Per-pixel seam cost map using character boundary avoidance.

    Generates high cost near foreground character edges (where BiRefNet says
    the pixel belongs to a character) so the DP seam is routed around them.

    Parameters
    ----------
    canvas_zone : (H_zone, W, 3) uint8 slice from the overlap zone.
    bg_mask_a/b : uint8 (H, W) background masks (255=background) for the two frames,
                  already warped to canvas space, sliced to the zone rows.
    dilate_px   : avoidance radius in pixels around foreground edges.

    Returns
    -------
    cost : (H_zone, W) float32 — 0 = seam-friendly, 1 = avoid.
    """
    zone_h, zone_w = canvas_zone.shape[:2]
    cost = np.zeros((zone_h, zone_w), dtype=np.float32)

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * dilate_px + 1, 2 * dilate_px + 1)
    )
    for bm in (bg_mask_a, bg_mask_b):
        if bm is None:
            continue
        fg = (bm < 127).astype(np.uint8) * 255  # foreground pixels
        # Edge of foreground mask → character silhouette
        edge = cv2.morphologyEx(
            fg, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        )
        # Dilate to create avoidance zone
        dilated = cv2.dilate(edge, kernel)
        cost = np.maximum(cost, (dilated > 0).astype(np.float32))

    return cost


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
    Deghost the temporal-median canvas by replacing animated foreground pixels
    with single-frame content.

    Background pixels are always kept from the temporal median (photometrically
    consistent across the whole canvas).  Only foreground character pixels are
    replaced with the single best owning frame, eliminating ghosting without
    introducing zone-level brightness discontinuities in the background.

    At ownership boundaries a Laplacian pyramid blend with a DP seam path is
    applied to foreground pixels only, providing a seamless character transition.
    """
    from .stateless import _laplacian_blend

    N = len(frames)
    print("[Stitch]   Laplacian-blend composite (foreground-only deghost)...")

    # For horizontal scrolls the strip_center_ys are all equal → all N-1 boundaries
    # pile up at canvas_h/2 → repeated overlapping Laplacian blends at the same row
    # produce a bright artefact band.  Temporal median is already correct for
    # horizontal scrolls (each pixel is covered by ≤2 frames so ghosting is minimal).
    tys = np.array([float(affines[i][1, 2]) for i in range(N)])
    txs = np.array([float(affines[i][0, 2]) for i in range(N)])
    ty_range = float(tys.max() - tys.min())
    tx_range = float(txs.max() - txs.min())
    if tx_range > 0 and ty_range / max(tx_range, 1.0) < 0.1:
        print(
            "[Stitch]   Horizontal scroll — temporal median is already optimal, skipping zone composite."
        )
        return canvas.copy()

    # Strip centres and ownership ordering
    strip_center_ys = np.array(
        [float(affines[i][1, 2]) + frames[i].shape[0] / 2.0 for i in range(N)],
        dtype=np.float64,
    )
    order = np.argsort(strip_center_ys)
    sorted_centers = strip_center_ys[order]
    initial_boundaries = (sorted_centers[:-1] + sorted_centers[1:]) / 2.0

    # Warp every frame to the full canvas.
    # INTER_LINEAR is intentional here: INTER_LANCZOS4's negative side-lobes produce
    # dark halos at sharp silhouette edges (character outline against black) that are
    # incorrectly classified as foreground content, creating staircase artifacts.
    warped_list: List[np.ndarray] = []
    for i in range(N):
        wf = cv2.warpAffine(
            frames[i],
            affines[i],
            (W, H),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        warped_list.append(wf)

    # Warp bg_masks to canvas space (True = background pixel).
    # Uncovered canvas positions default to background so they are never overwritten.
    warped_bg: List[Optional[np.ndarray]] = []
    for i in range(N):
        if bg_masks[i] is not None:
            wm = cv2.warpAffine(
                bg_masks[i].astype(np.uint8),
                affines[i],
                (W, H),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=255,
            )
            warped_bg.append(wm > 127)
        else:
            warped_bg.append(None)

    # Normalise every warped frame to a GLOBAL photometric reference computed from
    # the temporal median across all background pixels from all frames.
    #
    # Using the same absolute reference for every frame is critical: if each frame
    # normalised to "its own zone of the temporal median" independently, adjacent
    # zones could end up at different absolute brightness levels (because the median
    # itself may vary spatially if different-brightness frames dominate different
    # parts of the canvas).  A shared global reference guarantees all frames end up
    # on the same scale → no colour/brightness step at seam boundaries.
    #
    # Scalar luminance gain (not per-channel): corrects exposure without shifting hue.
    # Per-channel gain was introducing warm/red casts when backgrounds are dominated
    # by a strong hue (reddish dirt, orange firelight) — the skewed ref_mean would
    # over-boost the red channel and under-boost blue, altering the output colour.
    # BT.601 luminance weights for BGR: B=0.114, G=0.587, R=0.299.
    print("[Stitch]   Normalising warped frames to global temporal-median reference...")
    union_bg = np.zeros((H, W), dtype=bool)
    for wb in warped_bg:
        if wb is not None:
            union_bg |= wb

    global_ref_lum: Optional[float] = None
    ref_px = canvas[union_bg & (canvas.max(axis=2) > 10)]
    if len(ref_px) >= 500:
        global_ref_lum = float(ref_px.astype(np.float32).dot(LUMINANCE_WEIGHTS).mean())

    # Compute per-frame background luminance for coherence check
    frame_lums: List[Optional[float]] = []
    for i in range(N):
        if warped_bg[i] is not None:
            bg_sel = warped_bg[i] & (warped_list[i].max(axis=2) > 10)
            bg_px = warped_list[i][bg_sel]
            if len(bg_px) >= 200:
                frame_lums.append(float(bg_px.astype(np.float32).dot(LUMINANCE_WEIGHTS).mean()))
                continue
        frame_lums.append(None)

    # Inter-strip color coherence guard.
    # If adjacent frame strips (sorted by canvas position) differ by more than
    # _COHERENCE_LIMIT luminance units, partial gain correction (±7% clip) will not
    # bridge the gap and can actually increase visible banding by setting each strip
    # to a different absolute level.  In that case, skip normalization entirely and
    # let the temporal median stand — it already represents the multi-frame consensus.
    _COHERENCE_LIMIT = 20.0
    valid_lums = [l for l in frame_lums if l is not None]
    _skip_normalization = False
    if len(valid_lums) >= 2:
        lum_arr = np.array(valid_lums)
        _strip_spread = float(lum_arr.max() - lum_arr.min())
        # Also check adjacent-frame max diff (sorted by canvas row)
        lum_by_order = [frame_lums[int(order[k])] for k in range(N)]
        adj_diffs = [
            abs(lum_by_order[k + 1] - lum_by_order[k])
            for k in range(len(lum_by_order) - 1)
            if lum_by_order[k] is not None and lum_by_order[k + 1] is not None
        ]
        _max_adj_diff = float(max(adj_diffs)) if adj_diffs else 0.0
        if _max_adj_diff > _COHERENCE_LIMIT:
            _skip_normalization = True
            print(
                f"[Stitch]   Color coherence gate: max adjacent strip diff={_max_adj_diff:.1f} "
                f"> {_COHERENCE_LIMIT} → skipping per-frame normalization to prevent "
                f"amplifying color mismatch between animation frames."
            )
        else:
            print(f"[Stitch]   Color coherence OK (max adj diff={_max_adj_diff:.1f}). Applying normalization.")

    warped_norm: List[np.ndarray] = []
    for i in range(N):
        if not _skip_normalization and global_ref_lum is not None and warped_bg[i] is not None:
            bg_sel = warped_bg[i] & (warped_list[i].max(axis=2) > 10)
            bg_px = warped_list[i][bg_sel]
            if len(bg_px) >= 200 and frame_lums[i] is not None:
                # Tight clip — Stage 4.5 already applied ±14%; residual errors are small.
                # Applying a background-derived gain to foreground pixels amplifies natural
                # inter-frame luminance variation into hard brightness seams at ownership
                # boundaries.  Apply the gain to background pixels only; foreground pixels
                # retain their raw warped values so adjacent zones stay photometrically
                # consistent at character-outline boundaries.
                gain = float(np.clip(global_ref_lum / max(frame_lums[i], 1.0), 0.93, 1.07))
                f32 = warped_list[i].astype(np.float32)
                f32[bg_sel] = np.clip(f32[bg_sel] * gain, 0, 255)
                warped_norm.append(f32.astype(np.uint8))
                print(f"[Stitch]     Frame {i}: lum_gain={gain:.3f} (bg-only)")
                continue
        warped_norm.append(warped_list[i])

    # Single-pass boundary placement — use normalised frames for accurate diff scores
    print("[Stitch]   Optimising boundary placement...")
    boundaries, diff_scores = _find_optimal_boundaries(
        warped_norm,
        order,
        initial_boundaries,
        H,
        W,
        bg_masks=bg_masks,
        affines=affines,
    )
    feathers = np.array([_diff_to_feather(d) for d in diff_scores], dtype=np.int64)

    # Cap feathers by natural frame overlap so they never extend past real content
    n_b = len(boundaries)
    for k in range(n_b):
        fi_a = int(order[k])
        fi_b = int(order[k + 1])
        ty_a = float(affines[fi_a][1, 2])
        ty_b = float(affines[fi_b][1, 2])
        H_a = frames[fi_a].shape[0]
        H_b = frames[fi_b].shape[0]
        nat_overlap = max(0, int(min(ty_a + H_a, ty_b + H_b) - max(ty_a, ty_b)))
        max_feather = max(5, min(nat_overlap // 2, FEATHER_MAX))
        if feathers[k] > max_feather:
            feathers[k] = max_feather
    print(
        "[Stitch]   Feathers (overlap-capped): "
        + " ".join(f"B{k}={int(feathers[k])}px" for k in range(n_b))
    )

    # ── Stage 8.5: Foreground pose registration — global reference strategy ──
    # The camera model is translation-only, so the BACKGROUND is aligned in
    # warped_norm but the animating CHARACTER lands in two different poses on
    # either side of each ownership boundary → torn/doubled edges at the seam.
    #
    # Strategy: global reference pose (vs. pairwise midpoint).
    # We pick the temporally-central strip as the reference pose.  Every other
    # frame's foreground is warped TOWARD the reference at its seam boundary.
    # The warp fraction α decays with temporal distance from the reference so
    # the reference frame is never warped, nearby frames are warped a little,
    # and distant frames are warped more.  This prevents the drift accumulation
    # that pairwise midpoint warps accumulate across long strip chains.
    #
    # Fallback (A6): when the residual exceeds max_residual, take the seam-zone
    # foreground from the dominant pose frame only — no blending.
    seam_single_pose: dict = {}
    if _FG_REGISTER_ENABLED and N >= 2:
        try:
            from .fg_register import register_foreground_at_seam

            scroll_is_h = (tx_range > 0 and ty_range / max(tx_range, 1.0) < 0.1)
            reg_axis = 1 if scroll_is_h else 0

            # Reference index: the temporally-central frame in the sorted order.
            ref_idx_in_order = len(order) // 2
            ref_fi = int(order[ref_idx_in_order])

            n_warped = 0
            n_fallback = 0
            for k, by in enumerate(boundaries):
                fi_a = int(order[k])
                fi_b = int(order[k + 1])
                if warped_bg[fi_a] is None or warped_bg[fi_b] is None:
                    continue
                fg_a = ~warped_bg[fi_a]
                fg_b = ~warped_bg[fi_b]

                # Symmetric midpoint: both frames move halfway toward each other.
                # The global-reference approach (asymmetric alpha based on
                # distance from reference) amplifies noisy flow estimates for
                # frames far from the reference, causing regressions. Symmetric
                # midpoint is the safe default; the reference tracking is still
                # used for the ref= reporting/diagnostics.
                alpha_a = 0.5
                alpha_b = 0.5

                adj_a, adj_b, info = register_foreground_at_seam(
                    warped_norm[fi_a],
                    warped_norm[fi_b],
                    fg_a,
                    fg_b,
                    seam_pos=int(by),
                    axis=reg_axis,
                    alpha_a=alpha_a,
                    alpha_b=alpha_b,
                )
                if info["warped"]:
                    warped_norm[fi_a] = adj_a
                    warped_norm[fi_b] = adj_b
                    n_warped += 1
                    # Post-warp verification: if the foreground colour discrepancy
                    # at the seam is still large after ARAP warping, the two poses
                    # are too different to blend cleanly — escalate to single-pose
                    # so the blend zone doesn't create a double-image ghost.
                    post_diff = info.get("post_warp_diff", 0.0)
                    _POST_DIFF_THRESHOLD = 22.0  # lum units; empirically tuned
                    if post_diff > _POST_DIFF_THRESHOLD:
                        dom = fi_a if info["dominant"] == "a" else fi_b
                        seam_single_pose[k] = dom
                        n_fallback += 1
                        print(
                            f"[Stitch]     FG-register B{k} (frames {fi_a}/{fi_b}): "
                            f"residual={info['residual']:.1f}px post_diff={post_diff:.1f} "
                            f"→ re-posed BUT escalated to single-pose (ghost prevention)"
                        )
                    else:
                        print(
                            f"[Stitch]     FG-register B{k} (frames {fi_a}/{fi_b}): "
                            f"residual={info['residual']:.1f}px α=({alpha_a:.2f},{alpha_b:.2f}) "
                            f"post_diff={post_diff:.1f} fg_px={info['fg_pixels']} → re-posed"
                        )
                elif info.get("fallback"):
                    dom = fi_a if info["dominant"] == "a" else fi_b
                    seam_single_pose[k] = dom
                    n_fallback += 1
                    print(
                        f"[Stitch]     FG-register B{k} (frames {fi_a}/{fi_b}): "
                        f"residual={info['residual']:.1f}px too large → "
                        f"single-pose fallback (frame {dom})"
                    )
            print(
                f"[Stitch]   FG pose registration: {n_warped}/{n_b} re-posed, "
                f"{n_fallback}/{n_b} single-pose fallback. ref={ref_fi}"
            )
        except Exception as _fg_exc:
            print(f"[Stitch]   FG pose registration skipped ({_fg_exc}).")

    # Start from temporal median canvas — background pixels stay here permanently
    result = canvas.copy()

    # Hard-partition: write FOREGROUND pixels only from each ownership zone.
    # Background pixels are intentionally left as the temporal median so the
    # static scene elements (walls, floors, props) retain photometric consistency.
    for k in range(N):
        fi = int(order[k])
        y_start = 0 if k == 0 else int(boundaries[k - 1])
        y_end = H if k == N - 1 else int(boundaries[k])
        src = warped_norm[fi][y_start:y_end]
        has_content = src.max(axis=2) > 0
        if warped_bg[fi] is not None:
            is_fg = ~warped_bg[fi][y_start:y_end]  # foreground = not background
            replace = has_content & is_fg
        else:
            replace = has_content
        result[y_start:y_end][replace] = src[replace]

    # Laplacian blend at each boundary seam zone (foreground pixels only)
    for k, by in enumerate(boundaries):
        fi_a = int(order[k])
        fi_b = int(order[k + 1])
        feather = int(feathers[k])

        y0_f = max(0, int(by) - feather)
        y1_f = min(H, int(by) + feather + 1)
        zone_h = y1_f - y0_f
        if zone_h < 4:
            continue

        fa_zone = warped_norm[fi_a][y0_f:y1_f]
        fb_zone = warped_norm[fi_b][y0_f:y1_f]

        # P2.4 — Semantic seam routing: build a character-boundary cost map so
        # the DP path avoids cutting through foreground outlines.
        _bg_a_zone = warped_bg[fi_a][y0_f:y1_f] if warped_bg[fi_a] is not None else None
        _bg_b_zone = warped_bg[fi_b][y0_f:y1_f] if warped_bg[fi_b] is not None else None
        _sem_cost = _build_seam_cost_map(
            result[y0_f:y1_f],  # current canvas in zone
            ((_bg_a_zone.astype(np.uint8) * 255) if _bg_a_zone is not None else None),
            ((_bg_b_zone.astype(np.uint8) * 255) if _bg_b_zone is not None else None),
        )

        # DP seam path within the zone: path[col] = row in [0, zone_h-1]
        both = (fa_zone.max(axis=2) > 0) & (fb_zone.max(axis=2) > 0)
        if int(both.sum()) > zone_h * W // 20:
            try:
                path_local = _seam_cut(fa_zone, fb_zone, sem_cost=_sem_cost)
            except Exception:
                path_local = np.full(W, zone_h // 2, dtype=np.int32)
        else:
            path_local = np.full(W, zone_h // 2, dtype=np.int32)

        # P2.5 — Soft-seam diffusion blending (DSFN technique).
        # Instead of a fixed-width linear ramp, compute a spatially-adaptive blend
        # weight from the photometric similarity between the two frames in the zone.
        # High similarity (flat background) → wide, smooth transition.
        # Low similarity (character edge) → narrow, hard cut that preserves outlines.
        # The seam path still anchors the 50% iso-contour of the weight.
        # warped_bg[i] is True=background; pass background masks directly so the
        # seam weight can apply a tight cut at foreground pixels specifically.
        _wbg_a = warped_bg[fi_a][y0_f:y1_f] if warped_bg[fi_a] is not None else None
        _wbg_b = warped_bg[fi_b][y0_f:y1_f] if warped_bg[fi_b] is not None else None
        mask_float = _soft_seam_weight(
            fa_zone, fb_zone, path_local, zone_h, W,
            bg_mask_a=_wbg_a, bg_mask_b=_wbg_b,
        )

        blended = _laplacian_blend(fa_zone, fb_zone, mask_float)

        # Apply blend only to FOREGROUND pixels so background stays from temporal median.
        # Where both frames agree the pixel is background, leave the temporal median value.
        has_a = fa_zone.max(axis=2) > 0
        has_b = fb_zone.max(axis=2) > 0
        has_any = has_a | has_b

        if warped_bg[fi_a] is not None and warped_bg[fi_b] is not None:
            bg_a_z = warped_bg[fi_a][y0_f:y1_f]
            bg_b_z = warped_bg[fi_b][y0_f:y1_f]
            # Foreground in at least one frame — apply blend
            is_fg = ~(bg_a_z & bg_b_z)
            apply = has_any & is_fg
        else:
            is_fg = None
            apply = has_any

        # A6 — single-pose fallback: when the warp was unsafe at this seam, the
        # two frames hold the character in irreconcilable poses.  Blending them
        # produces a double image, so take the FOREGROUND from the dominant frame
        # only (background still blends).  The dominant frame's foreground pixels
        # win; the other frame fills only where the dominant has no content.
        _single = seam_single_pose.get(k)
        if _single is not None and is_fg is not None:
            dom_zone = warped_norm[_single][y0_f:y1_f]
            oth = fi_b if _single == fi_a else fi_a
            oth_zone = warped_norm[oth][y0_f:y1_f]
            dom_has = dom_zone.max(axis=2) > 0
            fg_apply = apply  # foreground pixels in the zone
            take_dom = fg_apply & dom_has
            take_oth = fg_apply & (~dom_has) & (oth_zone.max(axis=2) > 0)
            result[y0_f:y1_f][take_dom] = dom_zone[take_dom]
            result[y0_f:y1_f][take_oth] = oth_zone[take_oth]
            print(
                f"[Stitch]   Single-pose B{k} (frame {_single}): "
                f"zone=[{y0_f}–{y1_f}] fg_px={int(fg_apply.sum())} "
                f"(no blend — avoids double image)"
            )
        else:
            # Apply Laplacian blend only where BOTH frames have actual content.
            # At canvas boundary positions where only one frame has content, the
            # Laplacian pyramid creates ringing at the content-vs-zero transition.
            # For single-frame positions, take that frame directly.
            both_content = has_a & has_b & apply
            only_a = has_a & (~has_b) & apply
            only_b = (~has_a) & has_b & apply
            if both_content.any():
                result[y0_f:y1_f][both_content] = blended[both_content]
            if only_a.any():
                result[y0_f:y1_f][only_a] = fa_zone[only_a]
            if only_b.any():
                result[y0_f:y1_f][only_b] = fb_zone[only_b]
            print(
                f"[Stitch]   Blended B{k} (frames {fi_a}/{fi_b}): "
                f"zone=[{y0_f}–{y1_f}] feather={feather}px "
                f"seam=[{int(path_local.min())}–{int(path_local.max())}]"
            )

    # Fallback: fill remaining black pixels with content from any frame.
    # When frames have different horizontal extents (diagonal scroll), the warped
    # coverage areas create interior gaps not covered by the zone's owning frame.
    # These gaps would show as staircase black edges in the final image.  Any frame
    # that has content at the gap location is used to fill it.
    still_black = result.max(axis=2) == 0
    if still_black.any():
        for wn in warped_norm:
            has_content = (wn.max(axis=2) > 0) & still_black
            if has_content.any():
                result[has_content] = wn[has_content]
                still_black = result.max(axis=2) == 0
                if not still_black.any():
                    break

    return result


__all__ = ["_composite_foreground"]
