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

import concurrent.futures as _cf

from backend.src.animation.alignment.fg_register import register_foreground_at_seam
from backend.src.animation.core.stateless import _laplacian_blend

try:
    import base as batch
    if (
        getattr(batch, "__file__", None) is None
        or not hasattr(batch, "compositing")
    ):
        raise ImportError("compiled base.compositing extension not available")
    BATCH_AVAILABLE = True
except ImportError:
    batch = None
    BATCH_AVAILABLE = False

import os
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy.ndimage import minimum_filter1d as _min_filt1d

from backend.src.constants import (
    FEATHER_MAX,
    FEATHER_MIN,
    FEATHER_TABLE,
    LUMINANCE_WEIGHTS,
    SEAM_CROP_BAND_PX,
    SEARCH_RANGE,
    SEARCH_SLAB,
)

# §3.11 — Session-level seam ThreadPoolExecutor.  Creating a new pool per
# _composite_foreground call (311 tests × up to 4 workers) causes ~1 200
# pthread_create/join cycles that stall the Linux CFS scheduler.  One shared
# pool, created once on first use, eliminates all thread lifecycle overhead.
_SEAM_POOL: Optional["_cf.ThreadPoolExecutor"] = None


def _get_seam_pool() -> "_cf.ThreadPoolExecutor":
    global _SEAM_POOL
    if _SEAM_POOL is None:
        _SEAM_POOL = _cf.ThreadPoolExecutor(max_workers=4)
    return _SEAM_POOL


# Stage 8.5 foreground pose registration toggle (see fg_register.py).
# Enabled by default; set ASP_FG_REGISTER=0 to disable for A/B comparison.
_FG_REGISTER_ENABLED = os.environ.get("ASP_FG_REGISTER", "1") != "0"

# Phase 4 — cv::detail::GraphCutSeamFinder global multi-image seam.
# Default OFF (2026-07-09): the first full measurement of this path (5-test
# verify, post-trim) showed seam_visibility 20–80 vs the pairwise-DP path's
# ~26 S160 average — the hard ownership cut + ±8px feather without per-seam
# blocks gain compensation produces *more* visible seams than the wide-feather
# DP blend, not fewer.  Re-enable via ASP_GRAPHCUT_SEAM=1 only together with
# work on GC-boundary photometric correction, and benchmark before defaulting.
_GRAPHCUT_SEAM: bool = BATCH_AVAILABLE and os.environ.get("ASP_GRAPHCUT_SEAM", "0") != "0"

# §3.33 — Feather width (px) at GraphCut ownership boundaries.
# A narrow linear alpha ramp eliminates the 1-pixel luminance step at GC transitions.
# Set ASP_GC_FEATHER_PX=0 to disable; default 8px matches half the zone-edge guard width.
_GC_FEATHER_PX: int = int(os.environ.get("ASP_GC_FEATHER_PX", "8"))

# §1.27: Background pixel coverage minimum for normalisation.  The normalisation loop
# already guards with `len(bg_px) >= 200` before applying gain correction.  This flag
# makes that 200-pixel floor configurable — useful when the character fills most of the
# frame (sparse-bg scenes) and a tighter or looser threshold is needed.
# Default 0 → falls back to the built-in 200-pixel floor.
_BG_NORM_MIN_PX: int = int(os.environ.get("ASP_BG_NORM_MIN_PX", "0"))

# §1.106 — Post-composite seam luminance step audit (S152).
# After all seams are composited, measures the mean absolute lum step at each
# boundary row in the final output and logs warnings for large steps.
# ASP_POST_SEAM_WARN_THRESH sets the warning threshold (default 8.0 lum units).
# Always runs when boundaries are available (negligible overhead).
_POST_SEAM_WARN_THRESH: float = float(
    os.environ.get("ASP_POST_SEAM_WARN_THRESH", "8.0")
)

# §4.1 — Spatial blocks gain compensation (S160).
# After per-frame luminance normalisation, divide the blend zone into 32×32
# blocks and compute a per-block BGR gain ratio (fa/fb).  A bilinear-resized
# gain map (clamped [0.5, 2.0]) is applied to fb_zone before blending.
# Targets strip-level banding that the global scalar gain cannot handle.
# Default ON (§4.10 pre-seam equalization covers GraphCut; DP path also corrects).
_BLOCKS_GAIN_COMP: bool = os.environ.get("ASP_BLOCKS_GAIN_COMP", "1") != "0"

# §4.4 — Per-channel luminance blocks gain compensation (S160).
# Like §4.1 but uses the LAB L-channel ratio as a scalar gain applied to all
# BGR channels — avoids color cast from near-zero individual channel means.
# Default ON — LAB L-channel complement to BGR gain (no colour-cast risk).
_BLOCKS_LUM_COMP: bool = os.environ.get("ASP_BLOCKS_LUM_COMP", "1") != "0"

# §4.10 — Pre-seam global gain equalization (S165).
# Applied to ALL warped frames before GraphCut / DP seam finding.  Sequential
# pairwise _blocks_gain_compensate calls equalize inter-frame luminance to
# reduce strip_banding_score and seam_visibility.  Frame 0 (reference) unchanged.
# Only corrects pixels where BOTH adjacent frames have valid content (non-black).
# Default ON.  Set ASP_GLOBAL_GAIN_COMP=0 to disable.
_GLOBAL_GAIN_COMP: bool = os.environ.get("ASP_GLOBAL_GAIN_COMP", "1") != "0"


def _has_sufficient_bg(
    bg_sel: np.ndarray,
    min_px: int = 200,
) -> bool:
    """§1.27: Return True iff the background mask has at least *min_px* True pixels.

    The normalisation loop requires enough background pixels to compute a
    reliable mean luminance for gain estimation.  Below *min_px* the sample
    is too sparse and the estimated gain is noisy — particularly when the
    character fills most of the frame (portrait shots, tight cropping).

    Parameters
    ----------
    bg_sel:
        Boolean or uint8 mask; True/nonzero = background pixel.
    min_px:
        Minimum number of background pixels required for reliable estimation.
        Defaults to 200 (the historical hardcoded floor).

    Returns
    -------
    bool
        True when the background coverage is sufficient for normalisation.
    """
    if bg_sel is None:
        return False
    count = int(np.count_nonzero(bg_sel))
    return count >= max(1, min_px)


def _diff_to_feather(diff: float) -> int:
    for threshold, feather in FEATHER_TABLE:
        if diff <= threshold:
            return feather
    return FEATHER_MIN


def _gain_to_min_feather(gain_diff: float) -> int:
    """§1.6B: Minimum feather width from luminance gain difference (S22).

    When adjacent frames required significantly different gain corrections the
    normalization residual leaves a brightness step proportional to
    |gain_A − gain_B|.  Returns a floor feather wide enough to blend it:
    max(40, int(gain_diff × 300)), capped at 120 px.
    """
    return min(120, max(40, int(gain_diff * 300)))


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
    # Phase 5d: C++ fast path — GIL-released inner pixel loops, ~10–30× speedup
    if BATCH_AVAILABLE and hasattr(batch, "compositing") and hasattr(
        batch.compositing, "find_optimal_boundaries"
    ):
        try:
            _bg = None
            if bg_masks is not None:
                _bg = [
                    np.asarray(m, dtype=np.uint8) if m is not None else None
                    for m in bg_masks
                ]
            _bounds, _diffs = batch.compositing.find_optimal_boundaries(
                [np.ascontiguousarray(f) for f in warped_list],
                np.asarray(order, dtype=np.int64),
                np.asarray(initial_boundaries, dtype=np.float64),
                H, W,
                SEARCH_RANGE, SEARCH_SLAB,
                _bg, affines,
            )
            return np.asarray(_bounds), np.asarray(_diffs)
        except Exception:
            pass

    len(order)
    optimised = initial_boundaries.copy()
    diffs = np.full(len(initial_boundaries), float("inf"))

    # S17: Adaptive boundary search range.  For pure vertical-scroll sequences
    # (horizontal tx spread < 5 px) the optimal boundary is always very close
    # to the midpoint — a ±100 px window finds it safely and cuts 60 % of the
    # candidate evaluations for sparse sequences.  For diagonal/2D motion the
    # full ±SEARCH_RANGE is needed to reach the similarity minimum.
    _effective_range = SEARCH_RANGE
    if affines is not None and len(order) >= 2:
        _txs = np.array(
            [float(affines[int(order[i])][0, 2]) for i in range(len(order))],
            dtype=np.float32,
        )
        if float(np.ptp(_txs)) < 5.0:
            _effective_range = 100

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

        y_lo = max(lo_limit, int(by) - _effective_range)
        y_hi = min(hi_limit, int(by) + _effective_range)

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


def _compute_seam_energy(
    img1: np.ndarray,
    img2: np.ndarray,
    edge_weight: float,
    sem_cost: Optional[np.ndarray],
    sem_weight: float,
) -> np.ndarray:
    diff = cv2.absdiff(img1, img2).astype(np.float32).dot(LUMINANCE_WEIGHTS)
    gx_d = cv2.Sobel(diff, cv2.CV_32F, 1, 0, ksize=3)
    gy_d = cv2.Sobel(diff, cv2.CV_32F, 0, 1, ksize=3)
    energy = diff + 0.5 * (np.abs(gx_d) + np.abs(gy_d))

    for img in (img1, img2):
        gray = img.astype(np.float32).dot(LUMINANCE_WEIGHTS)
        gx_i = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy_i = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        energy += edge_weight * (np.abs(gx_i) + np.abs(gy_i))

    # P2.4 — Semantic character boundary avoidance
    if sem_cost is not None and sem_cost.shape == energy.shape:
        energy += sem_weight * sem_cost

    return energy


def _seam_cut_batch(
    img1: np.ndarray,
    img2: np.ndarray,
    edge_weight: float,
    sem_cost: Optional[np.ndarray],
    sem_weight: float,
    waypoints: Optional[List[Tuple[int, int]]],
) -> np.ndarray:
    w_list = []
    if waypoints:
        w_list = [-1] * img1.shape[1]
        for wx, wy in waypoints:
            if 0 <= wx < len(w_list):
                w_list[wx] = wy
    c_cost = (sem_cost * sem_weight) if sem_cost is not None else None
    return batch.seam.seam_cut(img1, img2, c_cost, w_list, 0.0, edge_weight)


def _prepare_waypoints(
    W_e: int,
    h_e: int,
    waypoints: Optional[List[Tuple[int, int]]],
) -> Tuple[Dict[int, int], np.ndarray]:
    wp_force: Dict[int, int] = {}
    wp_inf_mask = np.zeros((W_e, h_e), dtype=bool)
    if waypoints:
        for x_wp, y_wp in waypoints:
            if 0 <= x_wp < W_e and 0 <= y_wp < h_e:
                wp_force[x_wp] = y_wp
                wp_inf_mask[x_wp, :] = True
                wp_inf_mask[x_wp, y_wp] = False
    return wp_force, wp_inf_mask


def _seam_cut_python(
    img1: np.ndarray,
    img2: np.ndarray,
    edge_weight: float = 15.0,
    sem_cost: Optional[np.ndarray] = None,
    sem_weight: float = 200.0,
    waypoints: Optional[List[Tuple[int, int]]] = None,
) -> np.ndarray:
    """
    DP seam cut that strongly avoids outlines in *either* frame.

    Energy = diff(img1,img2) + grad(diff) + edge_weight*(edges_in_img1 + edges_in_img2)
             + sem_weight * sem_cost   (P2.4 — character boundary avoidance)

    Returns path[x] = y-offset in [0, h-1] for the minimum-energy horizontal
    cut running left→right across the (h × W × 3) slices.

    §2.11A: *waypoints* is an optional list of ``(x, y)`` pairs in zone-local
    coordinates (x = column 0..W-1, y = row 0..h-1).  Each waypoint forces the
    seam to pass through that exact pixel by setting all other rows in column x
    to ``+inf`` before the DP forward pass.  The seam then fans out from the
    forced pixel in subsequent columns, so 3-connectivity is preserved.
    """
    energy = _compute_seam_energy(img1, img2, edge_weight, sem_cost, sem_weight)

    # Transpose (h, W) → (W, h) so DP runs left→right; path[x] = y-offset
    E = energy.T.copy()
    W_e, h_e = E.shape

    # §2.11A: Intelligent Scissors waypoint injection.
    wp_force, wp_inf_mask = _prepare_waypoints(W_e, h_e, waypoints)
    E[wp_inf_mask] = np.inf

    # §1.5A: Vectorized DP forward pass.
    for i in range(1, W_e):
        E[i] += _min_filt1d(E[i - 1], size=3, mode="constant", cval=np.inf)

    # Traceback: avoid per-step Python list allocation by using slice argmin.
    path = np.empty(W_e, dtype=np.int32)
    j = wp_force.get(W_e - 1, int(E[W_e - 1].argmin()))
    path[W_e - 1] = j
    for i in range(W_e - 2, -1, -1):
        if i in wp_force:
            j = wp_force[i]  # §2.11A: hard-force seam through waypoint
        else:
            j_lo = max(0, j - 1)
            j_hi = min(h_e, j + 2)  # exclusive
            j = j_lo + int(E[i, j_lo:j_hi].argmin())
        path[i] = j
    return path  # path[x] in [0, zone_h-1]  — post-processing lives in _seam_cut


def _seam_cut(
    img1: np.ndarray,
    img2: np.ndarray,
    edge_weight: float = 15.0,
    sem_cost: Optional[np.ndarray] = None,
    sem_weight: float = 200.0,
    waypoints: Optional[List[Tuple[int, int]]] = None,
) -> np.ndarray:
    """Public seam-cut entry point.  Dispatches to C++ or Python DP backend,
    then re-applies §2.11A waypoint hard-pins so both backends behave
    identically in production."""
    if BATCH_AVAILABLE:
        path = _seam_cut_batch(img1, img2, edge_weight, sem_cost, sem_weight, waypoints)
    else:
        path = _seam_cut_python(img1, img2, edge_weight, sem_cost, sem_weight, waypoints)

    h_e = img1.shape[0]  # zone height (path rows are in [0, h_e-1])

    # §2.11A: re-apply waypoints so backend post-processing cannot displace
    # the user-specified seam positions.  Hard constraints win.
    if waypoints:
        W_e = img1.shape[1]
        for x_wp, y_wp in waypoints:
            if 0 <= x_wp < W_e and 0 <= y_wp < h_e:
                path[x_wp] = y_wp
    return path


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
    P2.5 / S17+S20 — Spatially-adaptive seam blend weight (DSFN technique).

    Returns (zone_h, W) float32 weight in [0, 1]:
      1.0 → fa_zone,  0.0 → fb_zone.

    S17: blend radius is now *per-pixel* rather than per-column-average.
    Each pixel gets a blend ramp proportional to its own local photometric
    similarity: background pixels (high similarity) get a wide, smooth
    transition; foreground pixels (low similarity at character edges) get a
    narrow cut automatically, without any separate fg-mask branch.  This is
    strictly more adaptive than the previous per-column mean — a column
    containing background rows at top and a character edge at the bottom row
    now gives those rows independently-sized ramps instead of the same average.

    S20: when *bg_mask_a* and *bg_mask_b* are provided, fg-vs-fg overlap pixels
    have their diffused similarity zeroed **after** the Gaussian diffusion step.
    This prevents background similarity from bleeding into character-vs-character
    overlap regions through the blur kernel.  Background pixels near the fg
    boundary still receive blended similarity from their neighbours, preserving
    the smooth background→edge gradient; only pixels where BOTH frames classify
    the pixel as foreground are forced to the narrow ramp (min_ramp_bg).
    """
    # Per-pixel L1 distance, mean over channels → (zone_h, W)
    diff = np.abs(fa_zone.astype(np.float32) - fb_zone.astype(np.float32)).mean(axis=2)
    # Similarity field: 1 where frames agree, 0 where they differ strongly
    similarity = np.exp(-diff / max(sigma, 1.0))
    # Anisotropic diffusion: Gaussian blur propagates similarity from flat areas
    sim_diffused = cv2.GaussianBlur(
        similarity, (0, 0), sigmaX=diffuse_sigma, sigmaY=diffuse_sigma
    )
    # S20: zero-out fg-vs-fg pixels *after* diffusion so that background
    # similarity cannot diffuse into character-vs-character overlap regions.
    # bg_mask: True = background pixel.  Only modifies pixels where BOTH frames
    # classify the pixel as foreground; bg-side edge pixels are untouched.
    if bg_mask_a is not None and bg_mask_b is not None:
        both_fg = (~bg_mask_a.astype(bool)) & (~bg_mask_b.astype(bool))
        if both_fg.any():
            sim_diffused[both_fg] = 0.0

    # S17: per-pixel blend ramp — each pixel drives its own transition width.
    # min_ramp_bg (10px) for low-similarity pixels; zone_h * 0.35 for high.
    min_ramp_bg = 10.0
    max_ramp_bg = max(min_ramp_bg + 1.0, zone_h * 0.35)
    ramp = (min_ramp_bg + sim_diffused * (max_ramp_bg - min_ramp_bg)).astype(
        np.float32
    )  # (zone_h, W) — was (1, W) via per-column mean before S17

    ys = np.arange(zone_h, dtype=np.float32)[:, np.newaxis]  # (zone_h, 1)
    seam_y = path_local[np.newaxis, :].astype(np.float32)  # (1, W)
    dist = ys - seam_y  # (zone_h, W)
    weight = np.clip(0.5 - dist / (2.0 * ramp), 0.0, 1.0).astype(np.float32)
    return weight


def _apply_exclusion_masks(
    cost: np.ndarray,
    exclusion_masks: Optional[List[np.ndarray]],
    zone_h: int,
    zone_w: int,
) -> np.ndarray:
    if exclusion_masks:
        for em in exclusion_masks:
            if em is None:
                continue
            em_zone = em
            if em.shape != (zone_h, zone_w):
                em_zone = cv2.resize(
                    em, (zone_w, zone_h), interpolation=cv2.INTER_NEAREST
                )
            cost[em_zone > 127] = 1e6
    return cost



def _build_seam_cost_map(
    canvas_zone: np.ndarray,
    bg_mask_a: Optional[np.ndarray],
    bg_mask_b: Optional[np.ndarray],
    dilate_px: int = 15,
    barrier_cost: Optional[float] = None,
    exclusion_masks: Optional[List[np.ndarray]] = None,
) -> np.ndarray:
    if (
        BATCH_AVAILABLE
        and barrier_cost is None
        and not exclusion_masks
        and dilate_px == 15              # C++ uses fixed 15px dilate
    ):
        _all_bg = np.full(canvas_zone.shape[:2], 255, dtype=np.uint8)
        ma = bg_mask_a if bg_mask_a is not None else _all_bg
        mb = bg_mask_b if bg_mask_b is not None else _all_bg
        # cost_map_norm=False: Python fallback never normalizes; keep tiers intact
        return batch.seam.build_seam_cost_map(canvas_zone, ma, mb, cost_map_norm=False)
    """
    P2.4 — Per-pixel seam cost map using character boundary avoidance (§1.6A S19).

    Issue 10A3 — exclusion_masks: list of uint8 (H_zone, W) masks (255=exclude).
    Each mask pixel where value > 127 gets cost=1e6 (hard barrier), forcing the
    DP seam to route around the named region. Generated by
    ``_detect_exclusion_mask(frame, "right arm")`` in grounding.py and injected
    after natural-language seam routing in the HITL MaskReviewDialog.

    Generates high cost near foreground character edges (where BiRefNet says
    the pixel belongs to a character) so the DP seam is routed around them.

    Tiered cost structure — creates a gradient that pulls the DP toward
    background corridors (§1.6A):
      Tier 1 — fg interior: cost = 1.0.  With sem_weight=200 in
      ``_seam_cut()``, every fg-interior pixel costs ≈ 200 energy units vs
      background pixels at ≈ 10–50.  Strongly deters the seam from
      bisecting the character body.
      Tier 2 — dilated fg edge buffer: cost = 0.5 (half of interior).
      Background pixels within ``dilate_px`` of any fg edge pay 100 energy —
      less than interior but more than clean background.  This gradient
      steers the DP THROUGH the edge-buffer zone toward background corridors,
      rather than treating the buffer identically to the body interior.

    Before S19, Tier 2 also used cost=1.0 (same as interior), so the DP had
    no incentive to route through the edge buffer on its way to background.

    If the character fills the full width and there is no all-background path,
    the DP gracefully degrades: it finds the minimum-cost path through the
    character body at its thinnest point.

    Parameters
    ----------
    canvas_zone : (H_zone, W, 3) uint8 slice from the overlap zone.
    bg_mask_a/b : uint8 (H, W) background masks (255=background) for the two frames,
                  already warped to canvas space, sliced to the zone rows.
    dilate_px   : avoidance radius in pixels around foreground edges.
    barrier_cost: cost applied to fg-dominated columns when a background corridor
                  exists (§1.23). *None* → uses module-level `_SEAM_HARD_BARRIER`
                  flag to choose between 2.0 (soft, S33 default) and
                  `_SEAM_HARD_BARRIER_COST` (1e6 hard barrier, S67).

    Returns
    -------
    cost : (H_zone, W) float32 — 0=bg seam-friendly, 0.5=fg edge buffer,
           1.0=fg interior, 2.0=fg-dominated column barrier (§3.15A).
           The column barrier fires only when background-corridor columns exist;
           when every column is fg-dominated the cost stays in {0, 0.5, 1.0}.
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

        # Tier 1 — fg interior: cost=1.0.
        cost = np.maximum(cost, (fg > 0).astype(np.float32))

        # Tier 2 — dilated fg edge buffer: cost=0.5 (§1.6A).
        # np.maximum preserves Tier 1 at 1.0 for fg pixels; only pure-background
        # pixels near fg edges are raised from 0 → 0.5.
        edge = cv2.morphologyEx(
            fg, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        )
        dilated = cv2.dilate(edge, kernel)
        cost = np.maximum(cost, (dilated > 0).astype(np.float32) * 0.5)

    # Tier 1.5 — fg-heavy columns: cost=1.5 (§1.126 FG_MAJORITY_FLOOR)
    zone_fg_frac = (cost >= 1.0).mean()
    if zone_fg_frac > 0.60:
        col_fg_frac = (cost >= 1.0).mean(axis=0)
        heavy = col_fg_frac > 0.80
        if heavy.any() and not heavy.all():
            cost[:, heavy] = np.maximum(cost[:, heavy], 1.5)

    # §3.15A SemanticStitch column barrier (S33) + §1.23 hard barrier upgrade (S67).
    # When a background corridor exists (some but not all columns are fg-dominated),
    # raise the dominated columns to `_barrier` so the DP is steered into the
    # corridor.  Soft mode (S33 default): 2.0 — discourages but does not block.
    # Fallback: when all columns are fg-dominated there is no corridor — skip the
    # filter so the DP finds the minimum-cost through-character path instead.
    _barrier = barrier_cost if barrier_cost is not None else 2.0
    fg_col_frac = (cost >= 1.0).mean(axis=0)
    dominated = fg_col_frac > 0.5
    if dominated.any() and not dominated.all():
        cost[:, dominated] = np.maximum(cost[:, dominated], _barrier)

    # Issue 10A3 — NL seam routing: inject hard-barrier exclusion masks.
    cost = _apply_exclusion_masks(cost, exclusion_masks, zone_h, zone_w)

    return cost


def _seam_color_match(
    dom_zone: np.ndarray,
    oth_zone: np.ndarray,
    path_local: np.ndarray,
    band_px: int,
) -> np.ndarray:
    """Shift *oth_zone* channel means to match *dom_zone* inside the seam band (S16).

    Computes per-channel mean luminance of content pixels within `band_px` rows
    of the seam path in each zone, then adds the per-channel delta to oth_zone's
    band pixels.  Pixels outside the band are returned unchanged.

    This reduces the color step at the seam centre from `post_warp_diff` lum
    units toward zero before the S15 linear ramp blend is applied, making the
    composite transition far less perceptible.  Safe to call even when
    `band_px == sp_soft_px` because the blend ramp weight approaches 0 at the
    band edge — the shift is smoothed away by the blend itself.

    Returns a (zone_h, W, C) uint8 copy of oth_zone with the band shifted.
    Unchanged copy returned when fewer than 10 content pixels exist in either
    zone's band (degenerate zone).
    """
    if band_px <= 0:
        return oth_zone.copy()
    zone_h, W = oth_zone.shape[:2]
    _row_idx = np.arange(zone_h, dtype=np.float32)[:, np.newaxis]
    _path_row = path_local[np.newaxis, :].astype(np.float32)
    _in_band = np.abs(_row_idx - _path_row) < band_px  # (zone_h, W) bool

    dom_content_mask = (dom_zone.max(axis=2) > 0) & _in_band
    oth_content_mask = (oth_zone.max(axis=2) > 0) & _in_band

    if dom_content_mask.sum() < 10 or oth_content_mask.sum() < 10:
        return oth_zone.copy()

    dom_mean = dom_zone[dom_content_mask].astype(np.float32).mean(axis=0)  # (C,)
    oth_mean = oth_zone[oth_content_mask].astype(np.float32).mean(axis=0)  # (C,)
    delta = dom_mean - oth_mean  # (C,)

    out = oth_zone.copy()
    shifted = oth_zone[_in_band].astype(np.float32) + delta
    out[_in_band] = np.clip(shifted, 0, 255).astype(np.uint8)
    return out


def _audit_seam_lum_steps(
    result: np.ndarray,
    boundaries: "List[float]",
    band_px: int = 5,
    warn_thresh: float = 8.0,
) -> "Dict[int, float]":
    """§1.106: Post-composite per-boundary luminance step audit (S152).

    For each boundary, measures mean absolute lum difference in a ±band_px
    row band around the boundary in *result*.  Logs a warning when any step
    exceeds *warn_thresh*.  Returns a dict {boundary_idx: lum_step}.
    """
    H = result.shape[0]
    steps: dict = {}
    for k, by_f in enumerate(boundaries):
        by = int(by_f)
        above_y0 = max(0, by - band_px)
        above_y1 = max(0, by)
        below_y0 = min(H, by)
        below_y1 = min(H, by + band_px)
        if above_y1 <= above_y0 or below_y1 <= below_y0:
            steps[k] = 0.0
            continue
        above_lum = float(
            result[above_y0:above_y1]
            .astype(np.float32)
            .dot(np.array([0.114, 0.587, 0.299], dtype=np.float32))
            .mean()
        )
        below_lum = float(
            result[below_y0:below_y1]
            .astype(np.float32)
            .dot(np.array([0.114, 0.587, 0.299], dtype=np.float32))
            .mean()
        )
        step = abs(above_lum - below_lum)
        steps[k] = step
        if step > warn_thresh:
            print(
                f"[Stitch] §1.106 seam-step WARNING: B{k} lum_step={step:.1f} "
                f"> {warn_thresh:.1f} at y={by}"
            )
    return steps


def _blocks_gain_compensate(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
    block_size: int = 32,
) -> np.ndarray:
    """§4.1: Spatial blocks gain compensation (S160).

    Divides the blend zone into *block_size* × *block_size* blocks and computes
    a per-block per-channel BGR gain ratio ``mean(fa_block) / mean(fb_block)``.
    A bilinear-resized (H, W, 3) gain map is applied to *fb_zone* to correct
    strip-level banding that global scalar gain normalisation cannot handle.
    Gain is clamped to [0.5, 2.0] before application.  Blocks where the
    fb-channel mean is < 1.0 (near-black) use gain=1.0 (safe no-op).

    Returns a uint8 copy of fb_zone with the spatial gain applied.
    """
    if fa_zone.size == 0 or fb_zone.size == 0:
        return fb_zone.copy()
    if BATCH_AVAILABLE and hasattr(batch, "compositing") and hasattr(
        batch.compositing, "blocks_gain_compensate_pair"
    ):
        try:
            return np.asarray(
                batch.compositing.blocks_gain_compensate_pair(fa_zone, fb_zone, block_size)
            )
        except Exception:
            pass
    H, W = fb_zone.shape[:2]
    bs = max(1, block_size)
    n_rows = max(1, (H + bs - 1) // bs)
    n_cols = max(1, (W + bs - 1) // bs)
    gain_grid = np.ones((n_rows, n_cols, 3), dtype=np.float32)
    for ri in range(n_rows):
        r0 = ri * bs
        r1 = min(r0 + bs, H)
        for ci in range(n_cols):
            c0 = ci * bs
            c1 = min(c0 + bs, W)
            fa_b = fa_zone[r0:r1, c0:c1].astype(np.float32)
            fb_b = fb_zone[r0:r1, c0:c1].astype(np.float32)
            for ch in range(3):
                m_fb = fb_b[:, :, ch].mean()
                m_fa = fa_b[:, :, ch].mean()
                gain_grid[ri, ci, ch] = (m_fa / m_fb) if m_fb >= 1.0 else 1.0
    gain_map = cv2.resize(gain_grid, (W, H), interpolation=cv2.INTER_LINEAR)
    gain_map = np.clip(gain_map, 0.5, 2.0)
    result = np.clip(fb_zone.astype(np.float32) * gain_map, 0, 255).astype(np.uint8)
    return result


def _blocks_lum_compensate(
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
    block_size: int = 32,
) -> np.ndarray:
    """§4.4: LAB L-channel blocks gain compensation (S160).

    Like ``_blocks_gain_compensate`` but uses the LAB L-channel ratio as a
    scalar gain applied uniformly to all BGR channels.  This avoids the colour
    cast that per-channel BGR gain can produce when any channel's mean is near
    zero in a block.  Gain clamped to [0.5, 2.0].

    Returns a uint8 copy of fb_zone with the spatial L-gain applied.
    """
    if fa_zone.size == 0 or fb_zone.size == 0:
        return fb_zone.copy()
    if BATCH_AVAILABLE and hasattr(batch, "compositing") and hasattr(
        batch.compositing, "blocks_lum_compensate_pair"
    ):
        try:
            return np.asarray(
                batch.compositing.blocks_lum_compensate_pair(fa_zone, fb_zone, block_size)
            )
        except Exception:
            pass
    H, W = fb_zone.shape[:2]
    fa_lab = cv2.cvtColor(fa_zone, cv2.COLOR_BGR2LAB).astype(np.float32)
    fb_lab = cv2.cvtColor(fb_zone, cv2.COLOR_BGR2LAB).astype(np.float32)
    bs = max(1, block_size)
    n_rows = max(1, (H + bs - 1) // bs)
    n_cols = max(1, (W + bs - 1) // bs)
    gain_grid = np.ones((n_rows, n_cols), dtype=np.float32)
    for ri in range(n_rows):
        r0 = ri * bs
        r1 = min(r0 + bs, H)
        for ci in range(n_cols):
            c0 = ci * bs
            c1 = min(c0 + bs, W)
            m_fb_l = float(fb_lab[r0:r1, c0:c1, 0].mean())
            m_fa_l = float(fa_lab[r0:r1, c0:c1, 0].mean())
            gain_grid[ri, ci] = m_fa_l / max(1.0, m_fb_l)
    gain_map = cv2.resize(gain_grid, (W, H), interpolation=cv2.INTER_LINEAR)
    gain_map = np.clip(gain_map, 0.5, 2.0)
    result = np.clip(
        fb_zone.astype(np.float32) * gain_map[:, :, np.newaxis], 0, 255
    ).astype(np.uint8)
    return result


def _single_pose_soft_edge(
    dom_zone: np.ndarray,
    oth_zone: np.ndarray,
    path_local: np.ndarray,
    apply_mask: np.ndarray,
    sp_soft_px: int,
) -> np.ndarray:
    """Narrow path-guided blend at a single-pose seam boundary (S15).

    Applies a linear feather of half-width *sp_soft_px* centred on
    *path_local* to smooth the hard color step between the dominant frame
    and the fill frame.  The zone is intentionally narrow (≤ 12 px at the
    default of 6) so pose-gap ghosts are not perceptible.

    Only pixels where BOTH frames have foreground content (non-zero) AND
    *apply_mask* is True AND distance to *path_local* < *sp_soft_px* are
    modified.  All other pixels are returned unchanged.

    Returns a (zone_h, W, C) uint8 copy of dom_zone with the blend applied.
    """
    zone_h, W = dom_zone.shape[:2]
    out = dom_zone.copy()
    if sp_soft_px <= 0:
        return out
    both_have = (dom_zone.max(axis=2) > 0) & (oth_zone.max(axis=2) > 0) & apply_mask
    if not both_have.any():
        return out
    _row_idx = np.arange(zone_h, dtype=np.float32)[:, np.newaxis]
    _path_row = path_local[np.newaxis, :].astype(np.float32)
    _dist = np.abs(_row_idx - _path_row)  # (zone_h, W)
    _in_band = (_dist < sp_soft_px) & both_have
    if not _in_band.any():
        return out
    _w_oth = (np.clip(1.0 - _dist / sp_soft_px, 0.0, 1.0) * 0.5)[:, :, np.newaxis]
    _blended = np.clip(
        dom_zone.astype(np.float32) * (1.0 - _w_oth)
        + oth_zone.astype(np.float32) * _w_oth,
        0,
        255,
    ).astype(np.uint8)
    out[_in_band] = _blended[_in_band]
    return out


def _adaptive_gain_clamp(ref_lum: float, frame_lum: float) -> float:
    """Scalar luminance gain with §1.4B continuous adaptive clip (S24).

    Clamp width linearly interpolates between ±26 % (pure-black scene) and
    ±14 % (pure-white scene): ``clamp_width = 0.26 - 0.12 × (ref_lum / 255)``.
    This removes the discontinuity at the S18 ref_lum=80 threshold while
    keeping the same endpoints ([0.86, 1.14] at ref=255).  Scalar (not
    per-channel) to avoid hue shift.
    """
    clamp_width = 0.26 - 0.12 * (ref_lum / 255.0)
    lo = 1.0 - clamp_width
    hi = 1.0 + clamp_width
    return float(np.clip(ref_lum / max(frame_lum, 1.0), lo, hi))


def _bg_gain_unclamped(
    ref_lum: float,
    frame_lum: float,
    override_threshold: float = 0.20,
) -> float:
    """§1.4C — Background-only gain that lifts the clamp when needed.

    When ``_adaptive_gain_clamp`` would reduce the ideal correction by more
    than ``override_threshold`` (default 20%), return the raw ideal gain so
    that background pixels receive the full correction.  For small deviations
    (clamp cut ≤ 20%) the clamped value is returned unchanged.

    Background pixels tolerate aggressive correction because:
    1. They are large uniform regions — clipping is less visible.
    2. Character skin tones (which motivated the clamp) are already excluded
       from the bg-only application site.

    Parameters
    ----------
    ref_lum : float
        Reference median background luminance (scene median, [0, 255]).
    frame_lum : float
        This frame's median background luminance.
    override_threshold : float
        Fraction of the ideal correction that the clamp may cut before we
        bypass it.  0.20 means the clamp may reduce the ideal by at most 20 %.
    """
    if frame_lum <= 0.0:
        return 1.0
    ideal = ref_lum / frame_lum
    clamped = _adaptive_gain_clamp(ref_lum, frame_lum)
    if ideal == 0.0:
        return clamped
    cut = abs(ideal - clamped) / abs(ideal)
    return ideal if cut > override_threshold else clamped


def _coherence_skip_mask(
    order: np.ndarray,
    frame_lums: "List[Optional[float]]",
    coherence_limit: float = 20.0,
) -> "List[bool]":
    """Per-frame normalization-skip mask from adjacent-strip coherence check (S18).

    Marks both frames in an adjacent pair as skip-normalization when their
    background luminance differs by more than *coherence_limit*.  Only the
    bad pair's frames are excluded — other frames proceed normally.  This
    replaces the former global-skip approach that penalised every frame when
    a single scene-change pair exceeded the limit.

    Returns a list of bool, one entry per frame index (not per order slot).
    """
    N = len(order)
    skip: "List[bool]" = [False] * N
    lum_by_order = [frame_lums[int(order[k])] for k in range(N)]
    for k in range(N - 1):
        la, lb = lum_by_order[k], lum_by_order[k + 1]
        if la is not None and lb is not None and abs(la - lb) > coherence_limit:
            skip[int(order[k])] = True
            skip[int(order[k + 1])] = True
    return skip


def _get_seam_cost_flags() -> Tuple:
    """§1.5D: Snapshot of module-level flags that affect seam cost computation."""
    return (_GRAPHCUT_SEAM,)


def _make_seam_cache_key(
    frame_keys: Optional[Tuple[str, ...]],
    k: int,
    cost_flags: Tuple,
) -> Optional[Tuple]:
    """§1.5D: Hashable cache key for seam boundary *k*.

    Returns *None* when *frame_keys* is None, disabling cache lookup/insertion.
    The key encodes frame identity, boundary index, and active cost flags so
    that changing a flag (e.g. enabling Poisson) correctly bypasses the cache.
    """
    if frame_keys is None:
        return None
    return (frame_keys, k, cost_flags)


def _extract_seam_crops(
    canvas: np.ndarray,
    boundaries: np.ndarray,
    band_px: int = SEAM_CROP_BAND_PX,
) -> Dict[int, np.ndarray]:
    """§2.4C — Crop ±band_px rows around each seam boundary from *canvas*.

    Returns a dict mapping seam index k → cropped subarray.  The crop is
    clamped to canvas bounds so edge seams produce narrower crops rather than
    raising an error.  Returns an empty dict when *boundaries* is empty or
    *canvas* has zero area.
    """
    result: Dict[int, np.ndarray] = {}
    if canvas.size == 0 or len(boundaries) == 0:
        return result
    H = canvas.shape[0]
    for k, by in enumerate(boundaries):
        y = int(by)
        y0 = max(0, y - band_px)
        y1 = min(H, y + band_px)
        result[k] = canvas[y0:y1].copy()
    return result


def _compute_initial_boundaries(
    affines: List[np.ndarray],
    frames: List[np.ndarray],
) -> np.ndarray:
    """Return midpoint y-coordinates between adjacent frame strip centres.

    Used by HITL checkpoint 3.5 to pre-compute boundary candidates for the
    boundary editor dialog before `_composite_foreground` is called.
    """
    N = len(frames)
    strip_center_ys = np.array(
        [float(affines[i][1, 2]) + frames[i].shape[0] / 2.0 for i in range(N)],
        dtype=np.float64,
    )
    order = np.argsort(strip_center_ys)
    sorted_centers = strip_center_ys[order]
    return (sorted_centers[:-1] + sorted_centers[1:]) / 2.0


def _feather_gc_boundaries(
    result: np.ndarray,
    ownership_masks: List[np.ndarray],
    warped_frames: List[np.ndarray],
    feather_px: int = 8,
) -> np.ndarray:
    """§3.33: Narrow feathered blend at GraphCut ownership transitions.

    For each adjacent pair (i, i+1) of ownership masks the per-column boundary
    row (last row owned by frame i) is found and a ±feather_px linear alpha ramp
    is blended between the two source frames.  Only pixels where both frames have
    content (non-black) are blended; all-black pixels are skipped so gap-fill work
    is not undone.
    """
    N = len(ownership_masks)
    if N < 2 or feather_px <= 0:
        return result
    out = result.copy()
    H, W = result.shape[:2]
    rows = np.arange(H, dtype=np.int32)[:, None]  # (H, 1) broadcast column
    for i in range(N - 1):
        own_i = (ownership_masks[i] > 127)
        has_col_i = own_i.any(axis=0)                    # (W,) — columns frame i owns
        last_row_i = (H - 1) - np.argmax(own_i[::-1], axis=0)  # last owned row per col
        boundary = np.where(has_col_i, last_row_i, -1)  # (W,) — -1 for unowned cols

        src_i    = warped_frames[i].astype(np.float32)
        src_next = warped_frames[i + 1].astype(np.float32)
        content_i    = warped_frames[i].max(axis=2) > 0   # (H, W)
        content_next = warped_frames[i + 1].max(axis=2) > 0

        b = boundary[None, :]  # (1, W)
        # alpha=1.0 → fully frame i; alpha=0.0 → fully frame i+1
        alpha = ((b + feather_px - rows) / (2.0 * feather_px)).clip(0.0, 1.0)
        in_band = (rows >= (b - feather_px)) & (rows <= (b + feather_px)) & (b >= 0)
        blend_here = in_band & content_i & content_next
        if not blend_here.any():
            continue
        alpha3 = alpha[:, :, None]
        blended = (alpha3 * src_i + (1.0 - alpha3) * src_next).clip(0, 255).astype(np.uint8)
        out[blend_here] = blended[blend_here]
    return out


def _equalize_warped_gains(
    warped_frames: List[np.ndarray],
    block_size: int = 32,
) -> List[np.ndarray]:
    """§4.10: Equalize inter-frame luminance before seam finding.

    Sequential pairwise gain compensation: frame 0 is the reference; each
    subsequent frame is corrected to match its (already-corrected) predecessor.
    Only pixels where BOTH adjacent frames have valid content (max channel > 0)
    are altered — black/transparent border fill regions are left untouched.
    """
    if len(warped_frames) < 2:
        return [f.copy() for f in warped_frames]
    result: List[np.ndarray] = [warped_frames[0].copy()]
    for i in range(1, len(warped_frames)):
        prev = result[i - 1]
        curr = warped_frames[i]
        has_prev = prev.max(axis=2) > 0
        has_curr = curr.max(axis=2) > 0
        both_valid = has_prev & has_curr
        if not both_valid.any():
            result.append(curr.copy())
            continue
        corrected = _blocks_gain_compensate(prev, curr, block_size=block_size)
        out = curr.copy()
        out[both_valid] = corrected[both_valid]
        result.append(out)
    return result


def _warp_inputs(
    frames: list,
    affines: list,
    bg_masks: list,
    H: int,
    W: int,
    N: int,
) -> tuple:
    # Warp every frame to the full canvas.
    warped_list = []
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
    warped_bg = []
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
    return warped_list, warped_bg


def _compute_frame_lums(
    warped_list: list,
    warped_bg: list,
    N: int,
) -> list:
    frame_lums = []
    for i in range(N):
        if warped_bg[i] is not None:
            bg_sel = warped_bg[i] & (warped_list[i].max(axis=2) > 10)
            bg_px = warped_list[i][bg_sel]
            if len(bg_px) >= 200:
                frame_lums.append(
                    float(bg_px.astype(np.float32).dot(LUMINANCE_WEIGHTS).mean())
                )
                continue
        frame_lums.append(None)
    return frame_lums


def _compute_skip_normalization_mask(
    order: np.ndarray,
    frame_lums: list,
    N: int,
) -> list:
    _COHERENCE_LIMIT = 20.0
    valid_lums = [lum for lum in frame_lums if lum is not None]
    _skip_norm = _coherence_skip_mask(order, frame_lums, _COHERENCE_LIMIT)
    if len(valid_lums) >= 2:
        lum_by_order = [frame_lums[int(order[k])] for k in range(N)]
        adj_diffs = [
            abs(lum_by_order[k + 1] - lum_by_order[k])
            for k in range(len(lum_by_order) - 1)
            if lum_by_order[k] is not None and lum_by_order[k + 1] is not None
        ]
        _max_adj_diff = max(adj_diffs) if adj_diffs else 0.0
        _n_skipped = sum(_skip_norm)
        if _n_skipped:
            print(
                f"[Stitch]   Color coherence gate (per-pair): max adj diff={_max_adj_diff:.1f}"
                f" → skipping normalization for {_n_skipped}/{N} frames in bad pairs."
            )
        else:
            print(
                f"[Stitch]   Color coherence OK (max adj diff={_max_adj_diff:.1f}). Applying normalization."
            )
    return _skip_norm


def _normalize_single_frame(
    i: int,
    canvas: np.ndarray,
    warped_list: list,
    warped_bg: list,
    _skip_norm: list,
    global_ref_lum: float,
    frame_lums: list,
) -> tuple:
    if (
        not _skip_norm[i]
        and global_ref_lum is not None
        and warped_bg[i] is not None
    ):
        bg_sel = warped_bg[i] & (warped_list[i].max(axis=2) > 10)
        _bg_min = _BG_NORM_MIN_PX if _BG_NORM_MIN_PX > 0 else 200
        if _has_sufficient_bg(bg_sel, _bg_min) and frame_lums[i] is not None:
            f32 = warped_list[i].astype(np.float32)
            gain = _bg_gain_unclamped(global_ref_lum, frame_lums[i])
            f32[bg_sel] = np.clip(f32[bg_sel] * gain, 0, 255)
            print(f"[Stitch]     Frame {i}: lum_gain={gain:.3f} (bg-only)")
            return f32.astype(np.uint8), gain
    return warped_list[i], 1.0


def _normalize_warped_frames(
    canvas: np.ndarray,
    warped_list: list,
    warped_bg: list,
    order: np.ndarray,
    N: int,
    H: int,
    W: int,
) -> tuple:
    print("[Stitch]   Normalising warped frames to global temporal-median reference...")
    union_bg = np.zeros((H, W), dtype=bool)
    for wb in warped_bg:
        if wb is not None:
            union_bg |= wb

    global_ref_lum = None
    ref_px = canvas[union_bg & (canvas.max(axis=2) > 10)]
    if len(ref_px) >= 500:
        global_ref_lum = float(ref_px.astype(np.float32).dot(LUMINANCE_WEIGHTS).mean())

    frame_lums = _compute_frame_lums(warped_list, warped_bg, N)
    _skip_norm = _compute_skip_normalization_mask(order, frame_lums, N)

    frame_gains = [1.0] * N
    warped_norm = []
    for i in range(N):
        wn, gain = _normalize_single_frame(
            i, canvas, warped_list, warped_bg, _skip_norm, global_ref_lum, frame_lums
        )
        warped_norm.append(wn)
        frame_gains[i] = gain

    return warped_norm, frame_gains


def _optimize_boundaries_and_feathers(
    warped_norm: list,
    order: np.ndarray,
    initial_boundaries: np.ndarray,
    bg_masks: list,
    affines: list,
    frames: list,
    frame_gains: list,
    warped_bg: list,
    H: int,
    W: int,
    N: int,
) -> tuple:
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
    max_feathers = []
    for k in range(n_b):
        fi_a = int(order[k])
        fi_b = int(order[k + 1])
        ty_a = float(affines[fi_a][1, 2])
        ty_b = float(affines[fi_b][1, 2])
        H_a = frames[fi_a].shape[0]
        H_b = frames[fi_b].shape[0]
        nat_overlap = max(0, int(min(ty_a + H_a, ty_b + H_b) - max(ty_a, ty_b)))
        max_feather = max(5, min(nat_overlap // 2, FEATHER_MAX))
        max_feathers.append(max_feather)
        if feathers[k] > max_feather:
            feathers[k] = max_feather
    print(
        "[Stitch]   Feathers (overlap-capped): "
        + " ".join(f"B{k}={int(feathers[k])}px" for k in range(n_b))
    )

    # §1.6B: Minimum feather from luminance gain difference at each boundary.
    _feather_gain_widened = False
    for k in range(n_b):
        fi_a = int(order[k])
        fi_b = int(order[k + 1])
        gain_diff = abs(frame_gains[fi_a] - frame_gains[fi_b])
        min_fk = _gain_to_min_feather(gain_diff)
        if feathers[k] < min_fk:
            feathers[k] = min(min_fk, max_feathers[k])
            _feather_gain_widened = True
    if _feather_gain_widened:
        print(
            "[Stitch]   Feathers (§1.6B gain-adjusted): "
            + " ".join(f"B{k}={int(feathers[k])}px" for k in range(n_b))
        )

    return boundaries, feathers


def _check_preemptive_escalations(
    k: int,
    by: float,
    fi_a: int,
    fi_b: int,
    fg_a: np.ndarray,
    fg_b: np.ndarray,
    affines: list,
    warped_norm: list,
    feathers: np.ndarray,
    seam_overrides: dict,
    seam_single_pose: dict,
    seam_post_diffs: dict,
    H: int,
) -> bool:
    # §2.4A: User seam override — force single-pose for this seam.
    _ov_k = (seam_overrides or {}).get(k, {})
    if _ov_k.get("force_single_pose"):
        _by_int_sp = int(by)
        _half_sp = min(20, int(feathers[k]))
        _y0_sp = max(0, _by_int_sp - _half_sp)
        _y1_sp = min(H, _by_int_sp + _half_sp)
        _fg_a_cnt_sp = int(fg_a[_y0_sp:_y1_sp].sum())
        _fg_b_cnt_sp = int(fg_b[_y0_sp:_y1_sp].sum())
        seam_single_pose[k] = fi_a if _fg_a_cnt_sp >= _fg_b_cnt_sp else fi_b
        seam_post_diffs[k] = 99.0  # sentinel: user-forced single-pose
        return True

    return False


def _apply_foreground_registration(
    k: int,
    by: float,
    fi_a: int,
    fi_b: int,
    fg_a: np.ndarray,
    fg_b: np.ndarray,
    warped_norm: list,
    warped_bg: list,
    feathers: np.ndarray,
    seam_single_pose: dict,
    seam_post_diffs: dict,
    reg_axis: int,
    alpha_a: float,
    alpha_b: float,
    ref_fi: int,
    _flow_ov: Optional[np.ndarray],
    H: int,
) -> None:
    adj_a, adj_b, info = register_foreground_at_seam(
        warped_norm[fi_a],
        warped_norm[fi_b],
        fg_a,
        fg_b,
        seam_pos=int(by),
        axis=reg_axis,
        alpha_a=alpha_a,
        alpha_b=alpha_b,
        flow_override=_flow_ov,
    )
    if info["warped"]:
        warped_norm[fi_a] = adj_a
        warped_norm[fi_b] = adj_b
        post_diff = info.get("post_warp_diff", 0.0)
        seam_post_diffs[k] = post_diff
        # A6 ghost-prevention: escalate to single-pose when the post-warp
        # residual is still large (fixed 22-lum threshold, benchmarked default).
        _sp_thresh = 22.0
        if post_diff > _sp_thresh:
            dom = fi_a if info["dominant"] == "a" else fi_b
            seam_single_pose[k] = dom
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
        seam_post_diffs[k] = float(info.get("residual", 0.0))
        print(
            "[Stitch]     FG-register B{k} (frames {fi_a}/{fi_b}): "
            f"residual={info['residual']:.1f}px too large → "
            f"single-pose fallback (frame {dom})"
        )


def _register_foreground_poses(
    warped_norm: list,
    warped_bg: list,
    order: np.ndarray,
    boundaries: np.ndarray,
    feathers: np.ndarray,
    affines: list,
    frames: list,
    seam_overrides: dict,
    ty_range: float,
    tx_range: float,
    H: int,
    W: int,
    N: int,
) -> tuple:
    seam_single_pose = {}
    seam_post_diffs = {}  # k → post-warp diff score (residual if fallback)
    seam_synthesized = {}  # retained for signature compatibility (always empty)
    if _FG_REGISTER_ENABLED and N >= 2:
        try:
            scroll_is_h = tx_range > 0 and ty_range / max(tx_range, 1.0) < 0.1
            reg_axis = 1 if scroll_is_h else 0

            # Reference index: the temporally-central frame in the sorted order.
            ref_idx_in_order = len(order) // 2
            ref_fi = int(order[ref_idx_in_order])

            for k, by in enumerate(boundaries):
                fi_a = int(order[k])
                fi_b = int(order[k + 1])
                if warped_bg[fi_a] is None or warped_bg[fi_b] is None:
                    continue
                fg_a = ~warped_bg[fi_a]
                fg_b = ~warped_bg[fi_b]

                if _check_preemptive_escalations(
                    k, by, fi_a, fi_b, fg_a, fg_b, affines, warped_norm, feathers, seam_overrides, seam_single_pose, seam_post_diffs, H
                ):
                    continue

                alpha_a = 0.5
                alpha_b = 0.5

                _apply_foreground_registration(
                    k, by, fi_a, fi_b, fg_a, fg_b, warped_norm, warped_bg, feathers,
                    seam_single_pose, seam_post_diffs, reg_axis, alpha_a, alpha_b, ref_fi, None, H
                )

        except Exception as _fg_exc:
            print(f"[Stitch]   FG pose registration skipped ({_fg_exc}).")

    return seam_single_pose, seam_post_diffs, seam_synthesized

def _composite_foreground(
    warped_corr: List[np.ndarray],
    warped_fgs: List[np.ndarray],
    canvas: np.ndarray,
    H: int,
    W: int,
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    bg_masks: List[Optional[np.ndarray]],
    frame_keys: Optional[Tuple[str, ...]] = None,
    seam_path_cache: Optional[Dict] = None,
    exclusion_masks: Optional[List[np.ndarray]] = None,
    preset_boundaries: Optional[np.ndarray] = None,
    paint_mask: Optional[np.ndarray] = None,
    seam_meta_out: Optional[dict] = None,
    seam_overrides: Optional[dict] = None,
) -> np.ndarray:
    N = len(frames)
    print("[Stitch]   Laplacian-blend composite (foreground-only deghost)...")

    # Scroll check
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
    if preset_boundaries is not None and len(preset_boundaries) == N - 1:
        initial_boundaries = np.asarray(preset_boundaries, dtype=np.float64)

    # Warp inputs
    warped_list, warped_bg = _warp_inputs(frames, affines, bg_masks, H, W, N)

    # Normalise warped frames
    warped_norm, frame_gains = _normalize_warped_frames(
        canvas, warped_list, warped_bg, order, N, H, W
    )

    # Optimize boundary placement and feathers
    boundaries, feathers = _optimize_boundaries_and_feathers(
        warped_norm, order, initial_boundaries, bg_masks, affines, frames, frame_gains, warped_bg, H, W, N
    )

    # Foreground pose registration
    seam_single_pose, seam_post_diffs, seam_synthesized = _register_foreground_poses(
        warped_norm, warped_bg, order, boundaries, feathers, affines, frames, seam_overrides, ty_range, tx_range, H, W, N
    )

    # Adaptive feather refinement and canonical crop synthesis
    seam_canonical_crops = _adapt_feathers_and_synthesize(
        seam_post_diffs, seam_single_pose, seam_synthesized, feathers, boundaries, order, affines, frames, warped_norm, H, W
    )

    # Equalise inter-frame luminance before seam finding.
    if _GLOBAL_GAIN_COMP and len(warped_norm) >= 2:
        warped_norm = _equalize_warped_gains(warped_norm, block_size=32)

    # Try global GraphCut / Canvas-space DP composite
    global_res = _try_global_seam_composite(
        warped_norm, warped_bg, canvas, H, W, N, boundaries,
        seam_post_diffs, seam_single_pose, seam_meta_out
    )
    if global_res is not None:
        return global_res

    # Hard-partition fill
    result = _initial_hard_partition_fill(
        canvas, warped_norm, warped_bg, order, boundaries, N, H
    )

    # Pre-compute seam DP paths
    _precomp_paths, _eff_exclusion = _precompute_seam_paths(
        result, boundaries, order, feathers, warped_norm, warped_bg,
        frame_keys, seam_path_cache, exclusion_masks, seam_overrides, paint_mask, H, W
    )

    # Laplacian blend at each boundary seam zone
    for k in range(len(boundaries)):
        by = boundaries[k]
        _process_single_seam(
            k, by, result, order, feathers, warped_norm, warped_bg,
            seam_single_pose, seam_post_diffs, seam_synthesized, seam_canonical_crops,
            seam_overrides, _precomp_paths, _eff_exclusion, seam_meta_out, H, W
        )

    # Post-composite audit and annotations
    result = _audit_and_annotate_composite(
        result, boundaries, order, feathers, warped_norm, _precomp_paths,
        seam_post_diffs, seam_single_pose, seam_meta_out
    )

    return result

def _adapt_feathers_and_synthesize(
    seam_post_diffs: dict,
    seam_single_pose: dict,
    seam_synthesized: dict,
    feathers: np.ndarray,
    boundaries: np.ndarray,
    order: np.ndarray,
    affines: List[np.ndarray],
    frames: List[np.ndarray],
    warped_norm: List[np.ndarray],
    H: int,
    W: int,
) -> dict:
    _feather_adapted = False
    n_b = len(boundaries)
    for _k, _pdiff in seam_post_diffs.items():
        if _k in seam_single_pose:
            continue
        if _pdiff < 8.0:
            feathers[_k] = min(int(feathers[_k] * 1.5), FEATHER_MAX)
            _feather_adapted = True
        elif _pdiff > 16.0:
            feathers[_k] = max(int(feathers[_k] * 0.75), FEATHER_MIN)
            _feather_adapted = True

    if _feather_adapted:
        for _k in range(n_b):
            _fi_a = int(order[_k])
            _fi_b = int(order[_k + 1])
            _ty_a = float(affines[_fi_a][1, 2])
            _ty_b = float(affines[_fi_b][1, 2])
            _H_a = frames[_fi_a].shape[0]
            _H_b = frames[_fi_b].shape[0]
            _nat_ov = max(0, int(min(_ty_a + _H_a, _ty_b + _H_b) - max(_ty_a, _ty_b)))
            _max_f = max(5, min(_nat_ov // 2, FEATHER_MAX))
            if feathers[_k] > _max_f:
                feathers[_k] = _max_f
        print(
            "[Stitch]   Feathers (post-FG-reg adapted): "
            + " ".join(f"B{_k}={int(feathers[_k])}px" for _k in range(n_b))
        )

    seam_canonical_crops: dict = {}
    return seam_canonical_crops


def _execute_graphcut_composite(
    warped_norm: List[np.ndarray],
    warped_bg: List[Optional[np.ndarray]],
    canvas: np.ndarray,
    H: int,
    W: int,
    N: int,
    boundaries: np.ndarray,
    seam_post_diffs: dict,
    seam_single_pose: dict,
    seam_meta_out: Optional[dict],
) -> np.ndarray:
    # Seam-estimation downscale (cv2.Stitcher runs GraphCut at seam_est_resol
    # ≈ 0.1 MPix; full-resolution min-cut over N frames is O(hours) on tall
    # canvases).  Find seams on a ≤ _GC_SEAM_EST_MPIX proxy, then upscale the
    # ownership masks back to canvas size with nearest-neighbour.
    _GC_SEAM_EST_MPIX = 0.4
    _scale = min(1.0, (_GC_SEAM_EST_MPIX * 1e6 / max(H * W, 1)) ** 0.5)
    if _scale < 1.0:
        _sw, _sh = max(8, int(W * _scale)), max(8, int(H * _scale))
        _gc_frames = [
            np.ascontiguousarray(
                cv2.resize(warped_norm[i], (_sw, _sh), interpolation=cv2.INTER_AREA)
            )
            for i in range(N)
        ]
    else:
        _gc_frames = [np.ascontiguousarray(warped_norm[i]) for i in range(N)]
    _gc_masks = [
        (f.max(axis=2) > 0).astype(np.uint8) * 255 for f in _gc_frames
    ]
    _gc_corners = [(0, 0)] * N
    print(
        f"[Stitch]   §4.2 GraphCut seam (global, {N} frames, "
        f"est scale={_scale:.2f})..."
    )
    _ownership = batch.seam.graphcut_seam_find(
        _gc_frames, _gc_masks, _gc_corners
    )
    if _scale < 1.0:
        _ownership = [
            cv2.resize(o, (W, H), interpolation=cv2.INTER_NEAREST)
            for o in _ownership
        ]
        _gc_frames = [np.ascontiguousarray(warped_norm[i]) for i in range(N)]
    result = canvas.copy()
    for i in range(N):
        own = _ownership[i] > 127
        src = warped_norm[i]
        has_content = src.max(axis=2) > 0
        _apply_gc = own & has_content
        if warped_bg[i] is not None:
            _apply_gc = _apply_gc & (~warped_bg[i])
        result[_apply_gc] = src[_apply_gc]

    _gc_black = result.max(axis=2) == 0
    if _gc_black.any():
        for _gcwn in warped_norm:
            _gc_fill = _gc_black & (_gcwn.max(axis=2) > 0)
            if _gc_fill.any():
                result[_gc_fill] = _gcwn[_gc_fill]
                _gc_black = result.max(axis=2) == 0
            if not _gc_black.any():
                break

    if _GC_FEATHER_PX > 0:
        result = _feather_gc_boundaries(result, _ownership, _gc_frames, feather_px=_GC_FEATHER_PX)

    if seam_meta_out is not None:
        seam_meta_out.update(
            {
                "boundaries": (
                    boundaries.tolist()
                    if hasattr(boundaries, "tolist")
                    else list(boundaries)
                ),
                "seam_post_diffs": dict(seam_post_diffs),
                "seam_single_pose": dict(seam_single_pose),
                "seam_crops": _extract_seam_crops(result, boundaries),
            }
        )
    print("[Stitch]   GraphCut composite done.")
    return result


def _try_global_seam_composite(
    warped_norm: List[np.ndarray],
    warped_bg: List[Optional[np.ndarray]],
    canvas: np.ndarray,
    H: int,
    W: int,
    N: int,
    boundaries: np.ndarray,
    seam_post_diffs: dict,
    seam_single_pose: dict,
    seam_meta_out: Optional[dict],
) -> Optional[np.ndarray]:
    if _GRAPHCUT_SEAM and BATCH_AVAILABLE and N >= 2:
        try:
            return _execute_graphcut_composite(
                warped_norm, warped_bg, canvas, H, W, N, boundaries,
                seam_post_diffs, seam_single_pose, seam_meta_out
            )
        except Exception as _gc_exc:
            print(
                f"[Stitch]   §4.2 GraphCut seam failed ({_gc_exc}), "
                "falling back to DP blend."
            )

    return None


def _initial_hard_partition_fill(
    canvas: np.ndarray,
    warped_norm: List[np.ndarray],
    warped_bg: List[Optional[np.ndarray]],
    order: np.ndarray,
    boundaries: np.ndarray,
    N: int,
    H: int,
) -> np.ndarray:
    result = canvas.copy()
    for k in range(N):
        fi = int(order[k])
        y_start = 0 if k == 0 else int(boundaries[k - 1])
        y_end = H if k == N - 1 else int(boundaries[k])
        src = warped_norm[fi][y_start:y_end]
        has_content = src.max(axis=2) > 0
        if warped_bg[fi] is not None:
            is_fg = ~warped_bg[fi][y_start:y_end]
            replace = has_content & is_fg
        else:
            replace = has_content
        result[y_start:y_end][replace] = src[replace]
    return result


def _prepare_seam_jobs(
    boundaries: np.ndarray,
    order: np.ndarray,
    feathers: np.ndarray,
    warped_norm: List[np.ndarray],
    warped_bg: List[Optional[np.ndarray]],
    frame_keys: Optional[Tuple[str, ...]],
    seam_path_cache: Optional[Dict],
    seam_overrides: Optional[dict],
    _eff_exclusion: Optional[List[np.ndarray]],
    _seam_cost_flags: dict,
    result: np.ndarray,
    H: int,
    W: int,
    _precomp_paths: dict,
) -> List[Tuple]:
    _seam_jobs = []
    for _k, _by in enumerate(boundaries):
        _ck = _make_seam_cache_key(frame_keys, _k, _seam_cost_flags)
        if _ck is not None and seam_path_cache is not None and _ck in seam_path_cache:
            _precomp_paths[_k] = seam_path_cache[_ck]
            continue
        _fi_a = int(order[_k])
        _fi_b = int(order[_k + 1])
        _f = int(feathers[_k])
        _y0 = max(0, int(_by) - _f)
        _y1 = min(H, int(_by) + _f + 1)
        if _y1 - _y0 < 4:
            continue
        _fa_z = warped_norm[_fi_a][_y0:_y1].copy()
        _fb_z = warped_norm[_fi_b][_y0:_y1].copy()
        _bg_a_z = warped_bg[_fi_a][_y0:_y1] if warped_bg[_fi_a] is not None else None
        _bg_b_z = warped_bg[_fi_b][_y0:_y1] if warped_bg[_fi_b] is not None else None
        _em_zone = [
            em[_y0:_y1]
            for em in (_eff_exclusion or [])
            if em is not None and em.shape[0] >= _y1
        ]
        _sem = _build_seam_cost_map(
            result[_y0:_y1].copy(),
            ((_bg_a_z.astype(np.uint8) * 255) if _bg_a_z is not None else None),
            ((_bg_b_z.astype(np.uint8) * 255) if _bg_b_z is not None else None),
            exclusion_masks=_em_zone or None,
        )
        _ov_wps_raw = (seam_overrides or {}).get(_k, {}).get("waypoints")
        _ov_wps = None
        if _ov_wps_raw:
            _ov_wps = [
                (int(x), int(y) - _y0)
                for x, y in _ov_wps_raw
                if 0 <= int(y) - _y0 < _y1 - _y0
            ]
        _seam_jobs.append((_k, _fa_z, _fb_z, _sem, W, _y1 - _y0, _ov_wps))
    return _seam_jobs


def _precompute_seam_paths(
    result: np.ndarray,
    boundaries: np.ndarray,
    order: np.ndarray,
    feathers: np.ndarray,
    warped_norm: List[np.ndarray],
    warped_bg: List[Optional[np.ndarray]],
    frame_keys: Optional[Tuple[str, ...]],
    seam_path_cache: Optional[Dict],
    exclusion_masks: Optional[List[np.ndarray]],
    seam_overrides: Optional[dict],
    paint_mask: Optional[np.ndarray],
    H: int,
    W: int,
) -> Tuple[dict, Optional[List[np.ndarray]]]:
    def _seam_job(job_args):
        _k, _fa_z, _fb_z, _sem, _W, _zh, _wps = job_args
        _both = (_fa_z.max(axis=2) > 0) & (_fb_z.max(axis=2) > 0)
        if int(_both.sum()) > _zh * _W // 20:
            try:
                return _k, _seam_cut(_fa_z, _fb_z, sem_cost=_sem, waypoints=_wps)
            except Exception:
                pass
        return _k, np.full(_W, _zh // 2, dtype=np.int32)

    _eff_exclusion = list(exclusion_masks or [])
    if paint_mask is not None and paint_mask.shape[0] == H and paint_mask.shape[1] == W:
        _eff_exclusion.append(paint_mask)
    _eff_exclusion = _eff_exclusion or None

    _seam_cost_flags = _get_seam_cost_flags()
    _precomp_paths: dict = {}
    _seam_jobs = _prepare_seam_jobs(
        boundaries, order, feathers, warped_norm, warped_bg, frame_keys,
        seam_path_cache, seam_overrides, _eff_exclusion, _seam_cost_flags,
        result, H, W, _precomp_paths
    )

    if len(_seam_jobs) > 1:
        _pool = _get_seam_pool()
        for _k, _path in _pool.map(_seam_job, _seam_jobs):
            _precomp_paths[_k] = _path
    elif _seam_jobs:
        _k, _path = _seam_job(_seam_jobs[0])
        _precomp_paths[_k] = _path

    if frame_keys is not None and seam_path_cache is not None:
        for _k, _path in _precomp_paths.items():
            _ck = _make_seam_cache_key(frame_keys, _k, _seam_cost_flags)
            if _ck not in seam_path_cache:
                seam_path_cache[_ck] = _path

    return _precomp_paths, _eff_exclusion


def _get_or_compute_path_local(
    k: int,
    y0_f: int,
    y1_f: int,
    zone_h: int,
    W: int,
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
    bg_a_zone: Optional[np.ndarray],
    bg_b_zone: Optional[np.ndarray],
    result_zone: np.ndarray,
    _precomp_paths: dict,
    _eff_exclusion: Optional[List[np.ndarray]],
    seam_overrides: Optional[dict],
) -> Tuple[np.ndarray, np.ndarray]:
    path_local = _precomp_paths.get(k)
    _em_zone_fb = [
        em[y0_f:y1_f]
        for em in (_eff_exclusion or [])
        if em is not None and em.shape[0] >= y1_f
    ]
    _sem_cost = _build_seam_cost_map(
        result_zone,
        (
            (bg_a_zone.astype(np.uint8) * 255)
            if bg_a_zone is not None
            else None
        ),
        (
            (bg_b_zone.astype(np.uint8) * 255)
            if bg_b_zone is not None
            else None
        ),
        exclusion_masks=_em_zone_fb or None,
    )
    if path_local is None:
        both = (fa_zone.max(axis=2) > 0) & (fb_zone.max(axis=2) > 0)
        if int(both.sum()) > zone_h * W // 20:
            try:
                _fb_wps_raw = (seam_overrides or {}).get(k, {}).get("waypoints")
                _fb_wps = None
                if _fb_wps_raw:
                    _fb_wps = [
                        (int(_wx), int(_wy) - y0_f)
                        for _wx, _wy in _fb_wps_raw
                        if 0 <= int(_wy) - y0_f < zone_h
                    ]
                path_local = _seam_cut(
                    fa_zone, fb_zone, sem_cost=_sem_cost, waypoints=_fb_wps
                )
            except Exception:
                path_local = np.full(W, zone_h // 2, dtype=np.int32)
        else:
            path_local = np.full(W, zone_h // 2, dtype=np.int32)

    return path_local, _sem_cost


def _fill_single_pose(
    k: int,
    y0_f: int,
    y1_f: int,
    zone_h: int,
    result: np.ndarray,
    fi_a: int,
    fi_b: int,
    warped_norm: List[np.ndarray],
    _single: int,
    seam_post_diffs: dict,
    path_local: np.ndarray,
    apply_mask: np.ndarray,
    feather: int,
):
    dom_zone = warped_norm[_single][y0_f:y1_f]
    oth = fi_b if _single == fi_a else fi_a
    oth_zone = warped_norm[oth][y0_f:y1_f]
    dom_has = dom_zone.max(axis=2) > 0
    fg_apply = apply_mask
    take_dom = fg_apply & dom_has
    take_oth = fg_apply & (~dom_has) & (oth_zone.max(axis=2) > 0)
    result[y0_f:y1_f][take_dom] = dom_zone[take_dom]
    result[y0_f:y1_f][take_oth] = oth_zone[take_oth]

    _eff_sp_soft_px = int(os.environ.get("ASP_SP_SOFT_PX", "6"))
    _band_px_sp = _eff_sp_soft_px + 4
    _oth_matched = _seam_color_match(
        dom_zone, oth_zone, path_local, _band_px_sp
    )
    _sp_zone = _single_pose_soft_edge(
        dom_zone, _oth_matched, path_local, fg_apply, _eff_sp_soft_px
    )
    _both_for_sp = dom_has & (oth_zone.max(axis=2) > 0) & fg_apply
    if _both_for_sp.any():
        result[y0_f:y1_f][_both_for_sp] = _sp_zone[_both_for_sp]

    print(
        f"[Stitch]   Single-pose B{k} (frame {_single}): "
        f"zone=[{y0_f}–{y1_f}] fg_px={int(fg_apply.sum())} "
        f"soft_px={_eff_sp_soft_px}"
    )


def _blend_or_single_pose_fill(
    k: int,
    y0_f: int,
    y1_f: int,
    zone_h: int,
    W: int,
    result: np.ndarray,
    fa_zone: np.ndarray,
    fb_zone: np.ndarray,
    fi_a: int,
    fi_b: int,
    warped_norm: List[np.ndarray],
    warped_bg: List[Optional[np.ndarray]],
    seam_single_pose: dict,
    seam_post_diffs: dict,
    seam_synthesized: dict,
    seam_canonical_crops: dict,
    path_local: np.ndarray,
    blended: np.ndarray,
    apply_mask: np.ndarray,
    is_fg: Optional[np.ndarray],
    feather: int,
):
    _single = seam_single_pose.get(k)
    if _single is not None and is_fg is not None:
        _fill_single_pose(
            k, y0_f, y1_f, zone_h, result, fi_a, fi_b, warped_norm,
            _single, seam_post_diffs, path_local, apply_mask, feather
        )
    else:
        has_a = fa_zone.max(axis=2) > 0
        has_b = fb_zone.max(axis=2) > 0
        both_content = has_a & has_b & apply_mask
        only_a = has_a & (~has_b) & apply_mask
        only_b = (~has_a) & has_b & apply_mask
        if both_content.any():
            result[y0_f:y1_f][both_content] = blended[both_content]
        if only_a.any():
            result[y0_f:y1_f][only_a] = fa_zone[only_a]
        if only_b.any():
            result[y0_f:y1_f][only_b] = fb_zone[only_b]
        print(
            f"[Stitch]   Blended B{k} (frames {fi_a}/{fi_b}, laplacian): "
            f"zone=[{y0_f}–{y1_f}] feather={feather}px "
            f"seam=[{int(path_local.min())}–{int(path_local.max())}]"
        )


def _process_single_seam(
    k: int,
    by: float,
    result: np.ndarray,
    order: np.ndarray,
    feathers: np.ndarray,
    warped_norm: List[np.ndarray],
    warped_bg: List[Optional[np.ndarray]],
    seam_single_pose: dict,
    seam_post_diffs: dict,
    seam_synthesized: dict,
    seam_canonical_crops: dict,
    seam_overrides: Optional[dict],
    _precomp_paths: dict,
    _eff_exclusion: Optional[List[np.ndarray]],
    seam_meta_out: Optional[dict],
    H: int,
    W: int,
):
    fi_a = int(order[k])
    fi_b = int(order[k + 1])
    feather = int(feathers[k])

    y0_f = max(0, int(by) - feather)
    y1_f = min(H, int(by) + feather + 1)
    zone_h = y1_f - y0_f
    if zone_h < 4:
        return

    fa_zone = warped_norm[fi_a][y0_f:y1_f]
    fb_zone = warped_norm[fi_b][y0_f:y1_f]
    bg_a_zone = warped_bg[fi_a][y0_f:y1_f] if warped_bg[fi_a] is not None else None
    bg_b_zone = warped_bg[fi_b][y0_f:y1_f] if warped_bg[fi_b] is not None else None

    path_local, sem_cost = _get_or_compute_path_local(
        k, y0_f, y1_f, zone_h, W, fa_zone, fb_zone, bg_a_zone, bg_b_zone, result[y0_f:y1_f],
        _precomp_paths, _eff_exclusion, seam_overrides
    )

    mask_float = _soft_seam_weight(
        fa_zone,
        fb_zone,
        path_local,
        zone_h,
        W,
        bg_mask_a=bg_a_zone,
        bg_mask_b=bg_b_zone,
    )

    _fb_for_blend = fb_zone
    if k not in seam_single_pose:
        if _BLOCKS_GAIN_COMP:
            _fb_for_blend = _blocks_gain_compensate(fa_zone, _fb_for_blend)
        if _BLOCKS_LUM_COMP:
            _fb_for_blend = _blocks_lum_compensate(fa_zone, _fb_for_blend)

    blended = _laplacian_blend(fa_zone, _fb_for_blend, mask_float)

    has_a = fa_zone.max(axis=2) > 0
    has_b = fb_zone.max(axis=2) > 0
    has_any = has_a | has_b

    if bg_a_zone is not None and bg_b_zone is not None:
        is_fg = ~(bg_a_zone & bg_b_zone)
        apply_mask = has_any & is_fg
    else:
        is_fg = None
        apply_mask = has_any

    _blend_or_single_pose_fill(
        k, y0_f, y1_f, zone_h, W, result, fa_zone, fb_zone, fi_a, fi_b,
        warped_norm, warped_bg, seam_single_pose, seam_post_diffs,
        seam_synthesized, seam_canonical_crops, path_local, blended,
        apply_mask, is_fg, feather
    )


def _fill_still_black_pixels(
    result: np.ndarray,
    warped_norm: List[np.ndarray],
):
    still_black = result.max(axis=2) == 0
    if still_black.any():
        for wn in warped_norm:
            has_content = (wn.max(axis=2) > 0) & still_black
            if has_content.any():
                result[has_content] = wn[has_content]
                still_black = result.max(axis=2) == 0
                if not still_black.any():
                    break


def _audit_and_annotate_composite(
    result: np.ndarray,
    boundaries: np.ndarray,
    order: np.ndarray,
    feathers: np.ndarray,
    warped_norm: List[np.ndarray],
    _precomp_paths: dict,
    seam_post_diffs: dict,
    seam_single_pose: dict,
    seam_meta_out: Optional[dict],
) -> np.ndarray:
    _fill_still_black_pixels(result, warped_norm)

    _seam_lum_steps = _audit_seam_lum_steps(
        result, boundaries, band_px=5, warn_thresh=_POST_SEAM_WARN_THRESH
    )
    _max_step = max(_seam_lum_steps.values()) if _seam_lum_steps else 0.0

    # §2.4A/C: Populate seam metadata dict for HITL checkpoint 4.6.
    if seam_meta_out is not None:
        seam_meta_out.update(
            {
                "seam_lum_steps": _seam_lum_steps,
                "max_seam_lum_step": _max_step,
                "boundaries": (
                    boundaries.tolist()
                    if hasattr(boundaries, "tolist")
                    else list(boundaries)
                ),
                "seam_post_diffs": dict(seam_post_diffs),
                "seam_single_pose": dict(seam_single_pose),
                "seam_crops": _extract_seam_crops(result, boundaries),
            }
        )

    return result


__all__ = [
    "_BG_NORM_MIN_PX",
    "_BLOCKS_GAIN_COMP",
    "_BLOCKS_LUM_COMP",
    "_FG_REGISTER_ENABLED",
    "_GC_FEATHER_PX",
    "_GLOBAL_GAIN_COMP",
    "_GRAPHCUT_SEAM",
    "_POST_SEAM_WARN_THRESH",
    "_SEAM_POOL",
    "_adapt_feathers_and_synthesize",
    "_adaptive_gain_clamp",
    "_apply_exclusion_masks",
    "_apply_foreground_registration",
    "_audit_and_annotate_composite",
    "_audit_seam_lum_steps",
    "_bg_gain_unclamped",
    "_blend_or_single_pose_fill",
    "_blocks_gain_compensate",
    "_blocks_lum_compensate",
    "_build_seam_cost_map",
    "_check_preemptive_escalations",
    "_coherence_skip_mask",
    "_composite_foreground",
    "_compute_frame_lums",
    "_compute_initial_boundaries",
    "_compute_seam_energy",
    "_compute_skip_normalization_mask",
    "_diff_to_feather",
    "_equalize_warped_gains",
    "_execute_graphcut_composite",
    "_extract_seam_crops",
    "_feather_gc_boundaries",
    "_fill_single_pose",
    "_fill_still_black_pixels",
    "_find_optimal_boundaries",
    "_gain_to_min_feather",
    "_get_or_compute_path_local",
    "_get_seam_cost_flags",
    "_get_seam_pool",
    "_has_sufficient_bg",
    "_initial_hard_partition_fill",
    "_make_seam_cache_key",
    "_normalize_single_frame",
    "_normalize_warped_frames",
    "_optimize_boundaries_and_feathers",
    "_precompute_seam_paths",
    "_prepare_seam_jobs",
    "_prepare_waypoints",
    "_process_single_seam",
    "_register_foreground_poses",
    "_seam_color_match",
    "_seam_cut",
    "_seam_cut_batch",
    "_seam_cut_python",
    "_single_pose_soft_edge",
    "_soft_seam_weight",
    "_try_global_seam_composite",
    "_warp_inputs",
]
