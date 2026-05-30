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

from typing import List, Optional, Tuple

import cv2
import numpy as np


_FEATHER_MAX = 300         # maximum feather half-width (low-diff boundaries)
_FEATHER_MIN = 80          # minimum feather half-width
_SEARCH_RANGE = 250        # px each side to search for optimal boundary placement
_SEARCH_SLAB = 20          # row height used when scoring candidate positions

# Adaptive feather: diff thresholds → target half-width.
_FEATHER_TABLE = [
    (5.0,  300),
    (10.0, 250),
    (20.0, 200),
    (35.0, 150),
    (50.0, 100),
    (float("inf"), _FEATHER_MIN),
]


def _diff_to_feather(diff: float) -> int:
    for threshold, feather in _FEATHER_TABLE:
        if diff <= threshold:
            return feather
    return _FEATHER_MIN


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

    frame_mean = warped[bg_mask].astype(np.float32).mean(axis=0)   # (3,)
    ref_mean   = canvas[bg_mask].astype(np.float32).mean(axis=0)   # (3,)

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

        lo_limit = int(optimised[k - 1]) + 2 * _SEARCH_SLAB + 1 if k > 0 else _SEARCH_SLAB
        hi_limit = (
            int(initial_boundaries[k + 1]) - 2 * _SEARCH_SLAB - 1
            if k < len(initial_boundaries) - 1
            else H - _SEARCH_SLAB - _SEARCH_SLAB
        )

        y_lo = max(lo_limit, int(by) - _SEARCH_RANGE)
        y_hi = min(hi_limit, int(by) + _SEARCH_RANGE)

        best_y = int(by)
        best_diff = float("inf")
        best_score = float("inf")

        bg_a = warped_bgs[fi_a]
        bg_b = warped_bgs[fi_b]

        for y_cand in range(y_lo, min(y_hi, H - _SEARCH_SLAB)):
            slab_a = warped_list[fi_a][y_cand : y_cand + _SEARCH_SLAB].astype(np.float32)
            slab_b = warped_list[fi_b][y_cand : y_cand + _SEARCH_SLAB].astype(np.float32)
            all_valid = (slab_a.max(axis=2) > 0) & (slab_b.max(axis=2) > 0)
            if all_valid.sum() < 50:
                continue

            all_d = float(np.abs(slab_a - slab_b).mean(axis=2)[all_valid].mean())

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

        half = _SEARCH_SLAB // 2
        y0_f = max(0, best_y - half)
        y1_f = min(H - 1, best_y + half)
        sa = warped_list[fi_a][y0_f:y1_f].astype(np.float32)
        sb = warped_list[fi_b][y0_f:y1_f].astype(np.float32)
        av = (sa.max(axis=2) > 0) & (sb.max(axis=2) > 0)
        total_diff = float(np.abs(sa - sb).mean(axis=2)[av].mean()) if av.sum() >= 10 else best_diff
        feather_metric = best_diff if (best_diff < 20.0 and total_diff < 20.0) else total_diff

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
    return path  # path[x] in [0, zone_h-1]


def _soft_seam_weight(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
    path_local: np.ndarray,
    zone_h: int,
    W: int,
    sigma: float = 15.0,
    diffuse_sigma: float = 20.0,
) -> np.ndarray:
    """
    P2.5 — Spatially-adaptive seam blend weight (DSFN technique).

    Returns (zone_h, W) float32 weight in [0, 1]:
      1.0 → fa_zone,  0.0 → fb_zone.

    The weight is derived from photometric similarity between the two frames:
    - Flat background regions (high similarity) get a wide, smooth transition.
    - Character edges (low similarity) get a narrow cut that preserves outlines.

    The seam path anchors the 0.5 iso-contour, then the similarity field
    stretches or shrinks the blend radius column-by-column.
    """
    # Per-pixel L1 distance, mean over channels → (zone_h, W)
    diff = np.abs(fa_zone.astype(np.float32) - fb_zone.astype(np.float32)).mean(axis=2)
    # Similarity field: 1 where frames agree, 0 where they differ strongly
    similarity = np.exp(-diff / max(sigma, 1.0))
    # Anisotropic diffusion: Gaussian blur propagates similarity from flat areas
    sim_diffused = cv2.GaussianBlur(similarity, (0, 0), sigmaX=diffuse_sigma, sigmaY=diffuse_sigma)
    # Blend radius per column (pixels): more similar → wider blend zone
    # Map sim ∈ [0,1] → ramp_px ∈ [10, zone_h * 0.35]
    min_ramp = 10.0
    max_ramp = max(min_ramp + 1.0, zone_h * 0.35)
    # Column-wise mean of diffused similarity → per-column ramp width
    col_sim = sim_diffused.mean(axis=0)  # (W,)
    ramp_per_col = (min_ramp + col_sim * (max_ramp - min_ramp)).astype(np.float32)

    ys = np.arange(zone_h, dtype=np.float32)[:, np.newaxis]  # (zone_h, 1)
    seam_y = path_local[np.newaxis, :].astype(np.float32)    # (1, W)
    dist = ys - seam_y                                         # (zone_h, W)
    ramp = ramp_per_col[np.newaxis, :]                        # (1, W)
    weight = np.clip(0.5 - dist / (2.0 * ramp), 0.0, 1.0).astype(np.float32)
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
        edge = cv2.morphologyEx(fg, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
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
        print("[Stitch]   Horizontal scroll — temporal median is already optimal, skipping zone composite.")
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
            frames[i], affines[i], (W, H),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT, borderValue=0,
        )
        warped_list.append(wf)

    # Warp bg_masks to canvas space (True = background pixel).
    # Uncovered canvas positions default to background so they are never overwritten.
    warped_bg: List[Optional[np.ndarray]] = []
    for i in range(N):
        if bg_masks[i] is not None:
            wm = cv2.warpAffine(
                bg_masks[i].astype(np.uint8), affines[i], (W, H),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT, borderValue=255,
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
    _LUM_W = np.array([0.114, 0.587, 0.299], dtype=np.float32)

    print("[Stitch]   Normalising warped frames to global temporal-median reference...")
    union_bg = np.zeros((H, W), dtype=bool)
    for wb in warped_bg:
        if wb is not None:
            union_bg |= wb

    global_ref_lum: Optional[float] = None
    ref_px = canvas[union_bg & (canvas.max(axis=2) > 10)]
    if len(ref_px) >= 500:
        global_ref_lum = float(ref_px.astype(np.float32).dot(_LUM_W).mean())

    warped_norm: List[np.ndarray] = []
    for i in range(N):
        if global_ref_lum is not None and warped_bg[i] is not None:
            bg_sel = warped_bg[i] & (warped_list[i].max(axis=2) > 10)
            bg_px = warped_list[i][bg_sel]
            if len(bg_px) >= 200:
                frame_lum = float(bg_px.astype(np.float32).dot(_LUM_W).mean())
                # Tight clip — Stage 4.5 already applied ±14%; residual errors are small.
                # Applying a background-derived gain to foreground pixels amplifies natural
                # inter-frame luminance variation into hard brightness seams at ownership
                # boundaries.  Apply the gain to background pixels only; foreground pixels
                # retain their raw warped values so adjacent zones stay photometrically
                # consistent at character-outline boundaries.
                gain = float(np.clip(global_ref_lum / max(frame_lum, 1.0), 0.93, 1.07))
                f32 = warped_list[i].astype(np.float32)
                f32[bg_sel] = np.clip(f32[bg_sel] * gain, 0, 255)
                warped_norm.append(f32.astype(np.uint8))
                print(f"[Stitch]     Frame {i}: lum_gain={gain:.3f} (bg-only)")
                continue
        warped_norm.append(warped_list[i])

    # Single-pass boundary placement — use normalised frames for accurate diff scores
    print("[Stitch]   Optimising boundary placement...")
    boundaries, diff_scores = _find_optimal_boundaries(
        warped_norm, order, initial_boundaries, H, W,
        bg_masks=bg_masks, affines=affines,
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
        max_feather = max(5, min(nat_overlap // 2, _FEATHER_MAX))
        if feathers[k] > max_feather:
            feathers[k] = max_feather
    print(
        "[Stitch]   Feathers (overlap-capped): "
        + " ".join(f"B{k}={int(feathers[k])}px" for k in range(n_b))
    )

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
            is_fg = ~warped_bg[fi][y_start:y_end]   # foreground = not background
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
        mask_float = _soft_seam_weight(fa_zone, fb_zone, path_local, zone_h, W)

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
            apply = has_any

        result[y0_f:y1_f][apply] = blended[apply]

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
