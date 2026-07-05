"""
backend/src/animation/frame_selection.py
====================================
Pose-consistent smart frame selection for the Anime Stitch Pipeline.

Problem
-------
Pan-shot anime contains two superimposed motions:
  T_camera  — rigid background translation (the camera panning)
  A_animation — non-rigid character articulation

Selecting frames based solely on camera displacement picks arbitrary animation
phases.  When consecutive selected frames show the character in different poses,
the seam-registration stage (Stage 8.5) must warp one pose toward the other.
The warp is only approximate, leaving residual edge-doubling ("ghost") artifacts.
The SSIM ceiling (test09: 0.787, test27: 0.709) is caused by this animation
timing mismatch, not by compositing quality.

Solution (§6.1 of the Upgrade Research report)
----------------------------------------------
Anime is animated "on twos" or "on threes" — the same character cel is held for
2–3 consecutive video frames.  Within these runs, the background has advanced by
the inter-frame camera step while the character pose is identical.  By detecting
these runs and selecting frames that match the previous anchor pose, we assemble
a panorama from geometrically coherent inputs before rendering begins.

The pose similarity metric is the mean absolute pixel difference on the
foreground region (BiRefNet-masked, per-frame gain-normalised).  Background
pixels are hard-thresholded out so camera-panning background structure
contributes nothing to the score.  Falls back to gradient-magnitude L1 on
the central 50% crop when BiRefNet masks are unavailable.

Algorithm
---------
1. Load all frames at thumbnail scale (no GPU, I/O-bound).
2. Phase-correlate consecutive thumbnails → cumulative canvas positions.
3. Greedy forward-selection with a pose-consistent lookahead window:
   - Accumulate candidates within [min_step_px, min_step_px + pose_window_px]
     of the last selected frame.
   - From the window, pick the candidate with the lowest central-crop L1
     distance to the last selected thumbnail (most pose-similar).
4. Always include the first and last frames.

Configuration
-------------
``ASP_POSE_WINDOW_PX`` (env, default "80") — window width in canvas pixels.
Set to "0" to revert to v1 first-past-threshold behaviour.
``ASP_TWO_CHANNEL_SELECT`` (env, default "0") — enable BiRefNet background mask
for camera displacement estimation (currently disabled; see note below).
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import os
from typing import List, Optional, Tuple

import cv2
import numpy as np

try:
    import base as _batch
    _BATCH_FSEL = True
except ImportError:
    _batch = None  # type: ignore[assignment]
    _BATCH_FSEL = False

# §3.14 — Optional ML imports: loaded only when DINOv2 / BiRefNet features are
# enabled at runtime.  Guarded so tests that don't use these paths don't pay
# the CUDA-context and model-weight initialisation overhead at collection time.
try:
    import torch
    import torch as _torch
    import torchvision.transforms as T
    from PIL import Image as _PIL_Image
except ImportError:
    torch = None  # type: ignore[assignment]
    _torch = None  # type: ignore[assignment]
    T = None  # type: ignore[assignment]
    _PIL_Image = None  # type: ignore[assignment]

# BiRefNetWrapper is imported lazily inside smart_select_frames when needed
# (birefnet_wrapper loads transformers at module level — §3.14).

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_SELECTOR_THUMB_LONG = 256  # thumbnail longest side for phase-correlation pass

# Pose-consistent refinement is disabled by default.  Session-5 upgraded the
# metric from gradient L1 (confounded by background scrolling) to fg-masked
# pixel L1 (background-invariant).  However GT-coupling still causes
# regressions on some tests: any frame substitution that diverges from the
# GT's temporal reference penalises SSIM.  Enable via ASP_POSE_WINDOW_PX=80
# for targeted experiments or when GT-SSIM is not the primary quality metric.
try:
    _POSE_WINDOW_PX = float(os.environ.get("ASP_POSE_WINDOW_PX", "0"))
except ValueError:
    _POSE_WINDOW_PX = 0.0

# Two-channel selection using BiRefNet background masks for cleaner camera
# displacement estimates.  Disabled by default — BiRefNet overhead is significant
# and the approach changed frame timing in ways that hurt GT-SSIM.
_TWO_CHANNEL_SELECT = os.environ.get("ASP_TWO_CHANNEL_SELECT", "0") != "0"
_PERIPH_BORDER_FRAC = 0.24

# §1A: Per-pair Otsu background mask for phase correlation.
# Faster and more accurate than the 5-probe BiRefNet intersection (_TWO_CHANNEL_SELECT)
# because each pair gets its own mask rather than sharing a static 5-probe estimate.
# Falls back to plain phaseCorrelate when the combined bg coverage < 10%.
# Default OFF — enable with ASP_OTSU_BG_CORR=1 or in asp_config.toml.
_OTSU_BG_CORR: bool = os.environ.get("ASP_OTSU_BG_CORR", "0") != "0"

# §3.5B — CamFlow background-masked phase correlation.
# ASP_CAMFLOW=bg_masked: use bg_masked_phase_correlate (cam_flow.py) on BiRefNet masks.
# Decouples camera displacement from character animation without frame-timing changes.
_CAMFLOW: str = os.environ.get("ASP_CAMFLOW", "")

# Animation hold detection — FD-Means preprocessing (§1.11 / §3.4).
# Default 0.025 corresponds to 2.5% mean absolute difference between
# consecutive thumbnails.  Within-hold frames typically score 0.003–0.010;
# cross-hold frames score 0.030–0.120.  Set ASP_HOLD_THRESHOLD=0 to disable.
try:
    _HOLD_THRESHOLD = float(os.environ.get("ASP_HOLD_THRESHOLD", "0.025"))
except ValueError:
    _HOLD_THRESHOLD = 0.025

# §1.2B: Near-duplicate post-filter for the selected frame list.
# Consecutive selected frames with mean grayscale diff < threshold are
# collapsed (first of each near-dup run kept; last frame always retained).
# Default 0.0 = disabled.  Enable with e.g. ASP_NEAR_DUP_LUMA=5.0.
try:
    _NEAR_DUP_LUMA = float(os.environ.get("ASP_NEAR_DUP_LUMA", "0.0"))
except ValueError:
    _NEAR_DUP_LUMA = 0.0

# §1.11C: Post-hoc hold refinement using phase-correlation response.
# If phaseCorrelate returns response >= this threshold, the two frames are
# near-identical (same character cel; MAD-based detection missed them due to
# MPEG noise), so merge their hold blocks.  Default 0.85.
# Set ASP_HIGH_HOLD_RESPONSE=0.0 to disable.
try:
    _HIGH_HOLD_RESPONSE = float(os.environ.get("ASP_HIGH_HOLD_RESPONSE", "0.85"))
except ValueError:
    _HIGH_HOLD_RESPONSE = 0.85

# §1.2D: Temporal variance filter — drops interior frames whose mean per-pixel
# variance across the (i-1, i, i+1) thumbnail triplet is below this threshold.
# Thumbnails are in [0, 1] float32.  Default 0.0 = disabled.
# Suggested value for enabling: 1e-3 (ASP_TEMPORAL_VAR_THRESH=0.001).
try:
    _TEMPORAL_VAR_THRESH = float(os.environ.get("ASP_TEMPORAL_VAR_THRESH", "0.0"))
except ValueError:
    _TEMPORAL_VAR_THRESH = 0.0

# §1.2E: Blur/artifact frame pre-rejection — Laplacian variance gate.
# Interior frames whose 64×64 thumbnail Laplacian variance (uint8 scale) is
# below the threshold are dropped before hold detection.  First/last always
# kept.  Default 0.0 = disabled.  Suggested value: ASP_BLUR_REJECT_THRESH=50.0.
try:
    _BLUR_REJECT_THRESH = float(os.environ.get("ASP_BLUR_REJECT_THRESH", "0.0"))
except ValueError:
    _BLUR_REJECT_THRESH = 0.0

# §1.46: Low-contrast frame pre-rejection — pixel std gate.
# Interior frames whose grayscale thumbnail std (in [0,255] scale) is below
# the threshold are dropped before hold detection.  Flash/whiteout/bloom frames
# have near-zero std — LoFTR and phase correlation have no texture to anchor on.
# Distinct from §1.2E (Laplacian blur): a sharp flash frame has high Laplacian
# but zero matchable texture.  First/last always kept.
# Default 0.0 = disabled.  Suggested value: ASP_CONTRAST_THRESH=15.0.
try:
    _CONTRAST_REJECT_THRESH = float(os.environ.get("ASP_CONTRAST_THRESH", "0.0"))
except ValueError:
    _CONTRAST_REJECT_THRESH = 0.0

# §3.4A: dHash hold detection — integer Hamming-distance threshold.
# 0 = disabled (use MAD-based detector).  Typical same-cel distance: 0–2;
# cross-cel: 5–20.  Enable with ASP_HOLD_DHASH_THRESH=4.
try:
    _HOLD_DHASH_THRESHOLD = int(os.environ.get("ASP_HOLD_DHASH_THRESH", "0"))
except ValueError:
    _HOLD_DHASH_THRESHOLD = 0

# §3.12A: Overmix hold-block sub-pixel averaging.
# After hold detection, align and stack-average all frames within each hold
# block using ECC (MOTION_TRANSLATION).  Produces one high-SNR representative
# per block; MPEG DCT compression noise cancels out by √N.
# Default OFF.  Enable with ASP_HOLD_AVERAGE=1.
_HOLD_AVERAGE: bool = os.environ.get("ASP_HOLD_AVERAGE", "0") != "0"


# ---------------------------------------------------------------------------
# Hold block detection
# ---------------------------------------------------------------------------


def _detect_hold_blocks(
    thumbs: List[np.ndarray],
    hold_threshold: float = 0.025,
) -> List[int]:
    """
    Detect animation "on twos / on threes" hold blocks and return the index of
    the first frame of each block.

    Anime animators draw a new character cel every 2–3 video frames
    (occasionally every frame for action shots, or every 4–6 for slow scenes).
    Within a hold block, consecutive frames are pixel-identical except for MPEG
    compression noise and sub-pixel camera drift.  At a hold boundary, the
    character snaps to a new pose → large pixel MAD.

    The detector compares consecutive thumbnail mean absolute differences
    (normalised to [0,1]).  If the MAD is below ``hold_threshold``, the two
    frames belong to the same hold block.  The first frame of each block is the
    representative.

    Parameters
    ----------
    thumbs : list of (H, W) float32 thumbnails in [0, 1].
    hold_threshold : mean absolute difference (in [0,1]) below which two
        consecutive thumbnails are considered the same cel.  Default 0.025
        (2.5% of [0,1] range).  Typical within-hold MAD: 0.003–0.010.
        Typical cross-hold MAD: 0.030–0.120.

    Returns
    -------
    List[int] — indices of the first frame of each hold block.  Each block
    represents one unique animation cel.  Length ≤ len(thumbs).

    Notes
    -----
    - For ``hold_threshold=0`` or len(thumbs) ≤ 1, returns list(range(N)).
    - This function is pure NumPy — no GPU, ~1ms for 300 frames.
    - Hold boundaries are the natural pose-change points (Sýkora 2009 §3.1).
      They provide a principled frame universe for Pass 2 pose-consistent
      refinement: candidates that cross exactly one hold boundary are
      guaranteed to show a different character pose (needed for ARAP to have
      useful work to do); candidates that stay within one hold are wasted
      (identical pose → ARAP residual ≈ 0, good — but selection is redundant).
    """
    N = len(thumbs)
    if hold_threshold <= 0.0 or N <= 1:
        return list(range(N))

    if _BATCH_FSEL:
        try:
            # C++ expects uint8; convert float32 [0,1] grayscale thumbnails
            u8 = [np.ascontiguousarray(
                      np.clip(t * 255, 0, 255).astype(np.uint8)
                      if t.dtype != np.uint8 else t)
                  for t in thumbs]
            # C++ returns indices of hold frames (MAD < threshold w.r.t. previous)
            hold_set = set(_batch.frame_selection.detect_hold_blocks_mad(
                u8, hold_threshold))
            return [i for i in range(N) if i not in hold_set]
        except Exception:
            pass

    blocks: List[int] = [0]
    for i in range(1, N):
        h = min(thumbs[i].shape[0], thumbs[i - 1].shape[0])
        w = min(thumbs[i].shape[1], thumbs[i - 1].shape[1])
        mad = float(
            np.mean(
                np.abs(
                    thumbs[i][:h, :w].astype(np.float32)
                    - thumbs[i - 1][:h, :w].astype(np.float32)
                )
            )
        )
        if mad > hold_threshold:
            blocks.append(i)

    return blocks


# ---------------------------------------------------------------------------
# dHash hold detection (§3.4A)
# ---------------------------------------------------------------------------


def _compute_dhash(
    thumb: np.ndarray,
    hash_size: int = 8,
) -> np.ndarray:
    """§3.4A: Difference hash (dHash) of a grayscale thumbnail.

    Resizes *thumb* to (hash_size+1, hash_size) pixels, then binarises the
    horizontal luminance gradient: column j is set to True when it is brighter
    than column j-1.  Returns a flat boolean array of ``hash_size²`` bits.

    Accepts float32 thumbnails in [0, 1] or uint8 thumbnails.  Resize uses
    INTER_AREA which averages out MPEG DCT-block noise before the comparison —
    the key advantage over MAD (which sees the raw noise).

    Parameters
    ----------
    thumb:
        Grayscale or colour thumbnail array.
    hash_size:
        Side length of the hash grid (default 8 → 64-bit hash).

    Returns
    -------
    np.ndarray of dtype bool, shape (hash_size²,).
    """
    src = np.clip(thumb * 255, 0, 255).astype(np.uint8) if thumb.dtype != np.uint8 else thumb
    if len(src.shape) == 3:
        src = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(src, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    return (small[:, 1:] > small[:, :-1]).flatten()


def _detect_hold_blocks_dhash(
    thumbs: List[np.ndarray],
    distance_threshold: int = 4,
) -> List[int]:
    """§3.4A: dHash-based animation hold detection.

    More robust to MPEG compression noise than the MAD detector
    (``_detect_hold_blocks``): the INTER_AREA resize averages DCT block
    artefacts before the directional comparison, so typical within-hold
    Hamming distance remains 0–2 even for aggressively-compressed sources
    where within-hold MAD can exceed the 0.025 default threshold.

    Parameters
    ----------
    thumbs:
        List of (H, W) or (H, W, C) thumbnail arrays.
    distance_threshold:
        Maximum Hamming distance (number of differing hash bits) for two
        consecutive frames to be considered the same animation hold.  When
        ``distance_threshold <= 0`` every frame starts a new block
        (equivalent to threshold = 0 for the MAD detector).

    Returns
    -------
    List[int] — indices of the first frame of each hold block.  Same return
    convention as ``_detect_hold_blocks``.
    """
    N = len(thumbs)
    if distance_threshold <= 0 or N <= 1:
        return list(range(N))

    if _BATCH_FSEL:
        try:
            u8 = [np.ascontiguousarray(
                      np.clip(t * 255, 0, 255).astype(np.uint8)
                      if t.dtype != np.uint8 else t)
                  for t in thumbs]
            hold_set = set(_batch.frame_selection.detect_hold_blocks_dhash(
                u8, 8, distance_threshold))
            return [i for i in range(N) if i not in hold_set]
        except Exception:
            pass

    hashes = [_compute_dhash(t) for t in thumbs]
    blocks: List[int] = [0]
    for i in range(1, N):
        dist = int(np.sum(hashes[i] != hashes[i - 1]))
        if dist > distance_threshold:
            blocks.append(i)
    return blocks


# ---------------------------------------------------------------------------
# Exact-duplicate dHash guard (§1.64)
# ---------------------------------------------------------------------------

# §1.64 — Exact-duplicate pHash guard (S129).
# Drops consecutive frames whose dHash Hamming distance is exactly 0 — these are
# pixel-identical at the thumbnail level and carry zero new canvas information.
# Distinct from §3.4A hold detection (which groups them) and §1.2D temporal
# variance filter (which operates in float space and can miss MPEG-exact duplicates
# that upsampled to uint8 round to identical thumbnails).
# This guard fires in step 0 of smart_select_frames, before any other filter.
# Default OFF (ASP_DHASH_EXACT_DROP=0).  Set to 1 to enable.
try:
    _DHASH_EXACT_DROP: bool = os.environ.get("ASP_DHASH_EXACT_DROP", "0") != "0"
except Exception:
    _DHASH_EXACT_DROP = False


def _drop_exact_dhash_duplicates(
    thumbs: List[np.ndarray],
    paths: List[str],
) -> "tuple[List[np.ndarray], List[str], int]":
    """§1.64: Drop consecutive frames that are pixel-identical at dHash scale (S129).

    Uses ``_compute_dhash`` (INTER_AREA resize, 64-bit hash) to detect
    exact duplicates: frames whose Hamming distance is **0** — every gradient
    bit matches.  When two consecutive frames have distance 0 the second frame
    is dropped (the first is kept as the canonical representative of that content).

    This is stricter than §3.4A hold detection (threshold ≤ 4) and earlier
    than §1.2D temporal variance — it eliminates true byte-level duplicates
    before any heavier processing runs.

    First and last frames are always retained, even if they are identical to
    their neighbours, to preserve canvas extent.

    Parameters
    ----------
    thumbs : list of (H, W) float32 thumbnails in [0, 1].  Length N.
    paths  : corresponding file paths.  Length N.

    Returns
    -------
    (filtered_thumbs, filtered_paths, n_dropped)
    """
    N = len(thumbs)
    if N < 3:
        return list(thumbs), list(paths), 0

    hashes = [_compute_dhash(t) for t in thumbs]
    keep = [True] * N
    for i in range(1, N - 1):
        if int(np.sum(hashes[i] != hashes[i - 1])) == 0:
            keep[i] = False

    n_dropped = keep.count(False)
    return (
        [t for t, k in zip(thumbs, keep, strict=False) if k],
        [p for p, k in zip(paths, keep, strict=False) if k],
        n_dropped,
    )


# ---------------------------------------------------------------------------
# Phase-correlation response hold refinement (§1.11C)
# ---------------------------------------------------------------------------


def _refine_hold_ids_by_response(
    hold_ids: List[int],
    responses: List[float],
    high_response_threshold: float = 0.85,
) -> "tuple[List[int], int]":
    """§1.11C — Post-hoc hold refinement using phase-correlation response.

    After phaseCorrelate runs for all cross-hold pairs, any pair whose response
    exceeds ``high_response_threshold`` represents near-identical frames that the
    MAD-based detector split into separate blocks due to MPEG compression noise.
    This function merges those blocks so that Pass 2 does not treat them as
    distinct character poses.

    Parameters
    ----------
    hold_ids:
        Per-frame hold block IDs produced by ``_detect_hold_blocks``.
        Length N (one entry per frame).
    responses:
        Phase-correlation response values from step 3.  Length N-1.
        Within-hold pairs already have response=1.0 (synthetic).
    high_response_threshold:
        Pairs with response >= this value are treated as the same cel.

    Returns
    -------
    (refined_hold_ids, n_hold_blocks)
    """
    N = len(hold_ids)
    if N < 2 or not responses:
        return list(hold_ids), len(set(hold_ids))

    ids = list(hold_ids)
    for i, resp in enumerate(responses):
        if i + 1 >= N:
            break
        # Only merge blocks that are currently split and have a high response
        if resp >= high_response_threshold and ids[i] != ids[i + 1]:
            old_id = ids[i + 1]
            new_id = ids[i]
            ids = [new_id if h == old_id else h for h in ids]

    # Renumber consecutively preserving first-occurrence order
    seen: dict = {}
    counter = 0
    result: List[int] = []
    for h in ids:
        if h not in seen:
            seen[h] = counter
            counter += 1
        result.append(seen[h])

    return result, len(seen)


# ---------------------------------------------------------------------------
# Temporal variance filter (§1.2D)
# ---------------------------------------------------------------------------


def _temporal_variance_filter(
    thumbs: List[np.ndarray],
    paths: List[str],
    sigma_threshold: float = 1e-3,
) -> "tuple[List[np.ndarray], List[str], int]":
    """§1.2D — Drop near-static interior frames using temporal variance across triplets.

    For each interior frame *i* (not first or last) compute the mean per-pixel
    variance across the consecutive thumbnail triplet
    (thumbs[i-1], thumbs[i], thumbs[i+1]).  Thumbnails are in [0, 1] float32.
    If the mean variance is below ``sigma_threshold``, the frame contributes no
    new motion information and is dropped.

    **Why this is different from the other near-dup filters:**
    - §1.2A / §1.2C operate on displacement edges — they require a non-zero
      match displacement to detect statics.
    - §1.2B compares *selected* frames post-selection.
    - §1.2D acts on the raw thumbnail sequence pre-selection, catching frames
      where both the camera and the character are stationary, regardless of
      whether the matching step would later produce a near-zero edge for them.

    First and last frames are always kept to preserve canvas extent.

    Parameters
    ----------
    thumbs:
        Grayscale float32 thumbnails in [0, 1].  Length N.
    paths:
        Corresponding frame file paths.  Length N.
    sigma_threshold:
        Mean per-pixel variance (in [0, 1]² space) below which a frame is
        considered static.  Default 1e-3 (approx. std ≈ 0.032, i.e., ~8 lum
        units of inter-frame noise amplitude).

    Returns
    -------
    (filtered_thumbs, filtered_paths, n_dropped)
    """
    N = len(thumbs)
    if N < 3 or sigma_threshold <= 0.0:
        return list(thumbs), list(paths), 0

    if _BATCH_FSEL:
        try:
            u8 = [np.ascontiguousarray(
                      np.clip(t * 255, 0, 255).astype(np.uint8)
                      if t.dtype != np.uint8 else t)
                  for t in thumbs]
            # C++ sigma_threshold is in [0,1]² space (same as Python)
            ft, fp = _batch.frame_selection.temporal_variance_filter(
                u8, list(paths), sigma_threshold)
            n_dropped = N - len(ft)
            # Recover original float32 thumb objects by path matching
            path_to_thumb = {p: t for p, t in zip(paths, thumbs, strict=False)}
            kept_thumbs = [path_to_thumb.get(p, u8[i]) for i, p in enumerate(fp)]
            return kept_thumbs, list(fp), n_dropped
        except Exception:
            pass

    keep = [True] * N
    for i in range(1, N - 1):
        a, b, c = thumbs[i - 1], thumbs[i], thumbs[i + 1]
        h = min(a.shape[0], b.shape[0], c.shape[0])
        w = min(a.shape[1], b.shape[1], c.shape[1])
        stack = np.stack([a[:h, :w], b[:h, :w], c[:h, :w]], axis=0)
        if float(np.mean(np.var(stack, axis=0))) < sigma_threshold:
            keep[i] = False

    n_dropped = keep.count(False)
    return (
        [t for t, k in zip(thumbs, keep, strict=False) if k],
        [p for p, k in zip(paths, keep, strict=False) if k],
        n_dropped,
    )


# ---------------------------------------------------------------------------
# Blur/artifact frame pre-rejection (§1.2E)
# ---------------------------------------------------------------------------


def _reject_blurry_frames(
    thumbs: List[np.ndarray],
    paths: List[str],
    blur_threshold: float,
    thumb_size: int = 64,
) -> "tuple[List[np.ndarray], List[str], int]":
    """§1.2E — Drop interior frames with Laplacian variance below blur_threshold.

    Resizes each grayscale float32 thumbnail to ``thumb_size``×``thumb_size``,
    converts to uint8, and measures the variance of the Laplacian.  Sharp frames
    produce high Laplacian variance; blurry or severe-artifact frames have low
    values because high-frequency edge energy is suppressed.

    First and last frames are always kept to preserve canvas extent.

    Parameters
    ----------
    thumbs:
        Grayscale float32 thumbnails in [0, 1].  Length N.
    paths:
        Corresponding frame file paths.  Length N.
    blur_threshold:
        Laplacian variance floor (uint8 scale, 0–255²).  Interior frames below
        this value are dropped.  0.0 = disabled (no frames dropped).
        Suggested: 50.0 for anime key-frames.
    thumb_size:
        Edge size for internal resize before Laplacian (default 64).

    Returns
    -------
    (filtered_thumbs, filtered_paths, n_dropped)
    """
    if blur_threshold <= 0.0 or len(thumbs) < 3:
        return list(thumbs), list(paths), 0

    keep = [True] * len(thumbs)
    for i in range(1, len(thumbs) - 1):
        small = cv2.resize(
            thumbs[i], (thumb_size, thumb_size), interpolation=cv2.INTER_AREA
        )
        gray_u8 = (np.clip(small, 0.0, 1.0) * 255).astype(np.uint8)
        lap_var = float(cv2.Laplacian(gray_u8, cv2.CV_32F).var())
        if lap_var < blur_threshold:
            keep[i] = False

    n_dropped = keep.count(False)
    return (
        [t for t, k in zip(thumbs, keep, strict=False) if k],
        [p for p, k in zip(paths, keep, strict=False) if k],
        n_dropped,
    )


# ---------------------------------------------------------------------------
# Low-contrast frame pre-rejection (§1.46)
# ---------------------------------------------------------------------------


def _reject_low_contrast_frames(
    thumbs: List[np.ndarray],
    paths: List[str],
    contrast_threshold: float,
) -> "tuple[List[np.ndarray], List[str], int]":
    """§1.46: Drop interior frames with pixel std below *contrast_threshold*.

    Measures contrast as the standard deviation of the grayscale thumbnail in
    the [0, 255] scale.  Near-uniform frames (flash panels, whiteout effects,
    bloom overexposure, fade-to-white transitions) produce std ≈ 0–10 lum
    units.  Such frames offer no reliable texture for LoFTR keypoint matching
    or phase-correlation peaks.

    This complements §1.2E (Laplacian blur): a sharp white-flash frame scores
    high Laplacian (crisp edges wherever the flash meets non-white content) but
    contributes zero matchable internal texture to the frame interior.

    First and last frames are always kept to preserve the canvas extent.

    Parameters
    ----------
    thumbs:
        Grayscale float32 thumbnails in [0, 1].  Length N.
    paths:
        Corresponding frame file paths.  Length N.
    contrast_threshold:
        Pixel std floor in [0, 255] units.  Interior frames below this value
        are dropped.  0.0 = disabled (returns inputs unchanged).
        Suggested: 15.0 for anime (flash frame std ≈ 0–8, normal frame ≈ 30–80).

    Returns
    -------
    (filtered_thumbs, filtered_paths, n_dropped)
    """
    if contrast_threshold <= 0.0 or len(thumbs) < 3:
        return list(thumbs), list(paths), 0

    keep = [True] * len(thumbs)
    for i in range(1, len(thumbs) - 1):
        gray_255 = np.clip(thumbs[i], 0.0, 1.0) * 255.0
        contrast = float(np.std(gray_255))
        if contrast < contrast_threshold:
            keep[i] = False

    n_dropped = keep.count(False)
    return (
        [t for t, k in zip(thumbs, keep, strict=False) if k],
        [p for p, k in zip(paths, keep, strict=False) if k],
        n_dropped,
    )


# ---------------------------------------------------------------------------
# Near-duplicate luma post-filter (§1.2B)
# ---------------------------------------------------------------------------


def _near_dup_luma_filter(
    selected_thumbs: List[np.ndarray],
    selected_paths: List[str],
    threshold: float = 5.0,
) -> List[str]:
    """
    §1.2B: Drop consecutive near-duplicate frames from the selected list.

    Compares each consecutive pair in the ALREADY-SELECTED frame list using
    mean absolute grayscale difference on thumbnail images.  When the diff is
    below ``threshold`` (luma units, 0–255 scale) the later frame is dropped —
    it adds negligible new content to the canvas and only introduces noise in
    bundle adjustment and the temporal median.

    The first frame is always kept.  The last frame is always retained even if
    it is a near-duplicate of the preceding frame (preserves full canvas extent).

    Set ``threshold=0.0`` to disable (returns ``selected_paths`` unchanged).
    Default is 5.0 luma units — catches camera steps well below the ~10-luma
    noise floor while leaving legitimate slow-scroll frames intact.
    """
    if threshold <= 0.0 or len(selected_paths) <= 2:
        return selected_paths

    if _BATCH_FSEL:
        try:
            # C++ expects uint8; thumbs from _load_thumbs_parallel are float32 [0,1]
            u8 = [
                (np.clip(t * 255, 0, 255).astype(np.uint8) if t.dtype != np.uint8 else t)
                for t in selected_thumbs
            ]
            _, kept_paths = _batch.frame_selection.near_dup_luma_filter(
                u8, list(selected_paths), float(threshold)
            )
            return list(kept_paths)
        except Exception:
            pass

    def _to_gray_f32(t: np.ndarray) -> np.ndarray:
        """Return float32 luma from 2D grayscale or 3D BGR thumb."""
        if t.ndim == 2:
            return t.astype(np.float32)
        return cv2.cvtColor(t, cv2.COLOR_BGR2GRAY).astype(np.float32)

    keep: List[int] = [0]
    # Determine threshold scale: float32 [0,1] thumbs need threshold in [0,1];
    # uint8 thumbs compare in [0,255] space directly.
    _is_float_thumb = selected_thumbs[0].dtype != np.uint8
    _thr_scaled = threshold / 255.0 if _is_float_thumb else threshold
    for i in range(1, len(selected_paths)):
        prev = keep[-1]
        g_cur = _to_gray_f32(selected_thumbs[i])
        g_prev = _to_gray_f32(selected_thumbs[prev])
        # Resize to common dims when thumbnails differ
        if g_cur.shape != g_prev.shape:
            h = min(g_cur.shape[0], g_prev.shape[0])
            w = min(g_cur.shape[1], g_prev.shape[1])
            g_cur = cv2.resize(g_cur, (w, h))
            g_prev = cv2.resize(g_prev, (w, h))
        diff = float(np.abs(g_cur - g_prev).mean())
        if diff >= _thr_scaled:
            keep.append(i)

    # Always include last frame
    last = len(selected_paths) - 1
    if keep[-1] != last:
        keep.append(last)

    return [selected_paths[i] for i in keep]


# ---------------------------------------------------------------------------
# Thumbnail I/O
# ---------------------------------------------------------------------------


def _load_thumb_gray(path: str) -> np.ndarray:
    """Load a grayscale float32 thumbnail for phase correlation."""
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return np.zeros((_SELECTOR_THUMB_LONG, _SELECTOR_THUMB_LONG), dtype=np.float32)
    h, w = img.shape
    scale = _SELECTOR_THUMB_LONG / max(h, w, 1)
    tw = max(1, int(w * scale))
    th = max(1, int(h * scale))
    return cv2.resize(img, (tw, th)).astype(np.float32) / 255.0


def _load_thumbs_parallel(
    frames_paths: List[str], max_workers: int = 8
) -> List[np.ndarray]:
    """Load thumbnails in parallel (I/O-bound; GIL released in cv2.imread)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(_load_thumb_gray, frames_paths))


def _otsu_bg_mask_pair(
    a: np.ndarray, b: np.ndarray, min_bg_frac: float = 0.10
) -> Optional[np.ndarray]:
    """§1A: per-pair Otsu background mask for bg-only phase correlation.

    Computes an Otsu threshold on each float32 grayscale thumbnail ([0,1]),
    treats pixels brighter than the threshold as background, then erodes
    both masks slightly to remove foreground-edge contamination.  Returns
    the pixel-wise minimum (intersection) so only pixels classified as
    background in BOTH frames are used for phase correlation.

    Returns None when the combined background coverage is below
    ``min_bg_frac`` (character fills most of the frame — no reliable signal).

    Parameters
    ----------
    a, b : (H, W) float32 thumbnails in [0, 1].
    min_bg_frac : minimum fraction of background pixels required to proceed.
    """
    erode_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    masks = []
    for thumb in (a, b):
        u8 = (thumb * 255.0).clip(0, 255).astype(np.uint8)
        thr, _ = cv2.threshold(u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # pixels > Otsu threshold are "light" — typically background in anime
        bg_u8 = (u8 > thr).astype(np.uint8) * 255
        bg_u8 = cv2.erode(bg_u8, erode_k)
        masks.append(bg_u8.astype(np.float32) / 255.0)
    combined = np.minimum(masks[0], masks[1])
    if float(combined.mean()) < min_bg_frac:
        return None
    return combined


# ---------------------------------------------------------------------------
# Pose similarity metric
# ---------------------------------------------------------------------------


def _fg_center_diff(
    thumb_a: np.ndarray,
    thumb_b: np.ndarray,
    fg_mask: Optional[np.ndarray] = None,
) -> float:
    """
    Pose similarity metric between two thumbnails.

    **With fg_mask (BiRefNet fg probability at thumbnail scale):**
    Hard-thresholds the mask (> 0.3) to a binary fg_bin, zeroes out all
    background pixels, then computes mean absolute pixel difference on the
    foreground region.  Each frame's fg pixels are independently normalised to
    zero mean / unit std before differencing to remove inter-frame gain
    variations (ECC gain normalisation has not yet run at selection time).

    This is strictly background-invariant: background pixels are exactly 0.0 in
    both masked images, so camera-panning locker/wall/scenery structure
    contributes nothing to the score regardless of mask softness.  For "on
    twos" animation holds (same character cel for 2–3 consecutive frames),
    fg pixels look identical → score ≈ 0.  Across a hold boundary (new
    animation cel), fg pixels shift position → score > 0.

    The previous gradient-weighted approach computed the Sobel gradient on the
    full image and multiplied by fg_mask, so background edges (lockers, walls)
    with fg_mask weight of 0.05–0.1 still contributed proportionally.  This
    masked-pixel approach is background-invariant by construction.

    **Without fg_mask (fallback):**
    Gradient-magnitude L1 on the central 50% crop.  Partly confounded by
    background structure but does not require BiRefNet.

    Returns a non-negative float (0 = identical character region).
    """
    h = min(thumb_a.shape[0], thumb_b.shape[0])
    w = min(thumb_a.shape[1], thumb_b.shape[1])

    if fg_mask is not None and fg_mask.shape[0] >= h and fg_mask.shape[1] >= w:
        fg_bin = (fg_mask[:h, :w] > 0.3).astype(np.float32)
        total = float(fg_bin.sum())
        if total >= 50.0:
            a = thumb_a[:h, :w]
            b = thumb_b[:h, :w]
            # Per-frame fg normalisation to remove gain variation
            a_px = a[fg_bin > 0.5]
            b_px = b[fg_bin > 0.5]
            a_norm = (a - float(a_px.mean())) / (float(a_px.std()) + 1e-5)
            b_norm = (b - float(b_px.mean())) / (float(b_px.std()) + 1e-5)
            diff = np.abs(a_norm - b_norm) * fg_bin
            return float(diff.sum() / total)
        # fg mask too sparse — fall through to central-crop

    # Fallback: gradient-magnitude L1 on central 50% crop
    def _grad_mag(img: np.ndarray) -> np.ndarray:
        gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
        return np.sqrt(gx * gx + gy * gy)

    h0, h1 = h // 4, 3 * h // 4
    w0, w1 = w // 4, 3 * w // 4
    if h1 <= h0 or w1 <= w0:
        a, b = thumb_a[:h, :w], thumb_b[:h, :w]
    else:
        a, b = thumb_a[h0:h1, w0:w1], thumb_b[h0:h1, w0:w1]
    return float(np.mean(np.abs(_grad_mag(a) - _grad_mag(b))))


# ---------------------------------------------------------------------------
# DINOv2 Pose Features
# ---------------------------------------------------------------------------

# Module-level model cache — avoids reloading DINOv2 on every benchmark test
# (96 tests × 10–30s reload = 15–48 minutes of avoidable overhead).
# Key: device string; Value: (model, transform) tuple.
_DINOV2_CACHE: dict = {}


def _compute_dinov2_features(frames_paths: List[str]) -> Optional[np.ndarray]:
    """
    Compute DINOv2 (ViT-S/14) pose embeddings for all frames.

    Returns (N, 384) float32 array of L2-normalised feature vectors, or None
    if DINOv2 is unavailable (no torch.hub access, model weights not cached, etc.).

    The model is loaded once per process and cached in ``_DINOV2_CACHE`` — the
    first call to this function per device incurs the hub-load overhead
    (~5–30s); subsequent calls are instantaneous.

    DINOv2 features are used in Pass 2 of ``smart_select_frames()`` as the
    pose similarity metric.  Cosine distance between frame features captures
    pose difference robustly:
      - Animation holds (same cel, 2–3 consecutive frames) → distance ≈ 0.02–0.05
      - Cross-hold transitions (new cel) → distance ≈ 0.10–0.30
      - Different scenes → distance > 0.50

    This is background-invariant by design: DINOv2 was trained on diverse
    natural images and its ViT features are dominated by semantic content
    (pose, character shape) rather than background texture patterns.
    """
    try:
        device = "cuda" if (torch is not None and torch.cuda.is_available()) else "cpu"

        if device not in _DINOV2_CACHE:
            model = (
                torch.hub.load(
                    "facebookresearch/dinov2", "dinov2_vits14", verbose=False
                )
                .to(device)
                .eval()
            )
            transform = T.Compose(
                [
                    T.Resize(224, interpolation=T.InterpolationMode.BICUBIC),
                    T.CenterCrop(224),
                    T.ToTensor(),
                    T.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
                ]
            )
            _DINOV2_CACHE[device] = (model, transform)

        model, transform = _DINOV2_CACHE[device]
    except Exception:
        return None

    # Batch-process frames: load, optionally crop to fg bounding box, stack, infer.
    tensors = []
    try:
        with torch.no_grad():
            for path in frames_paths:
                img = _PIL_Image.open(path).convert("RGB")

                # §1D — foreground-masked DINOv2: crop to the BiRefNet foreground
                # bounding box before embedding.  Background pixels dominate the
                # ViT attention on pan-shot anime where the scene is >80% bg,
                # causing DINOv2 to track camera translation rather than pose.
                # Cropping to the fg bbox removes the background from the input
                # and forces the network to attend to character shape and pose.
                try:
                    _img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                    # Cheap fg estimate: pixels far from the median hue are
                    # character (anime backgrounds are mostly monotone gradient).
                    _gray = cv2.cvtColor(_img_bgr, cv2.COLOR_BGR2GRAY)
                    _h, _w = _gray.shape
                    # Use Otsu binarisation to separate fg/bg in luminance
                    _, _fg_bin = cv2.threshold(
                        _gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
                    )
                    _ys, _xs = np.where(_fg_bin > 0)
                    if len(_ys) > (_h * _w * 0.05):  # at least 5% fg pixels
                        _y0, _y1 = int(_ys.min()), int(_ys.max())
                        _x0, _x1 = int(_xs.min()), int(_xs.max())
                        # Add 5% padding
                        _pad_y = max(8, int((_y1 - _y0) * 0.05))
                        _pad_x = max(8, int((_x1 - _x0) * 0.05))
                        _y0 = max(0, _y0 - _pad_y)
                        _y1 = min(_h, _y1 + _pad_y)
                        _x0 = max(0, _x0 - _pad_x)
                        _x1 = min(_w, _x1 + _pad_x)
                        if (_y1 - _y0) > 32 and (_x1 - _x0) > 32:
                            img = img.crop((_x0, _y0, _x1, _y1))
                except Exception:
                    pass  # fg crop is best-effort; fall back to full frame

                tensors.append(transform(img))

            # Stack and infer in one forward pass (more efficient than per-frame)
            batch = torch.stack(tensors).to(model.parameters().__next__().device)
            feats = model(batch)  # (N, 384)
            feats = feats / feats.norm(dim=-1, keepdim=True)
            return feats.cpu().numpy().astype(np.float32)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# §3.12A: Overmix hold-block averaging
# ---------------------------------------------------------------------------


def _hold_block_average(
    frames: List[np.ndarray],
    hold_ids: List[int],
    paths: List[str],
) -> Tuple[List[np.ndarray], List[str]]:
    """Compress hold blocks into one ECC-aligned average frame each.

    For MPEG-compressed sources, MPEG DCT block noise cancels out by √N when N
    frames within the same animation hold are stack-averaged after sub-pixel ECC
    alignment.  Singletons are returned unchanged.
    """
    from collections import OrderedDict

    blocks: OrderedDict[int, List[int]] = OrderedDict()
    for idx, hid in enumerate(hold_ids):
        blocks.setdefault(hid, []).append(idx)

    out_frames: List[np.ndarray] = []
    out_paths: List[str] = []

    for indices in blocks.values():
        if len(indices) == 1:
            out_frames.append(frames[indices[0]])
            out_paths.append(paths[indices[0]])
            continue

        ref = frames[indices[0]].astype(np.float32)
        ref_gray = cv2.cvtColor(frames[indices[0]], cv2.COLOR_BGR2GRAY).astype(
            np.float32
        )
        stack = [ref]
        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 1e-3)
        warp_init = np.eye(2, 3, dtype=np.float32)

        for i in indices[1:]:
            src_gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY).astype(np.float32)
            try:
                _, warp = cv2.findTransformECC(
                    ref_gray,
                    src_gray,
                    warp_init.copy(),
                    cv2.MOTION_TRANSLATION,
                    criteria,
                )
                aligned = cv2.warpAffine(
                    frames[i].astype(np.float32),
                    warp,
                    (ref.shape[1], ref.shape[0]),
                    flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                )
                stack.append(aligned)
            except cv2.error:
                stack.append(frames[i].astype(np.float32))

        avg = np.mean(stack, axis=0).clip(0, 255).astype(np.uint8)
        out_frames.append(avg)
        mid = indices[len(indices) // 2]
        out_paths.append(paths[mid])

    return out_frames, out_paths


# ---------------------------------------------------------------------------
# Main selector
# ---------------------------------------------------------------------------


def smart_select_frames(
    frames_paths: List[str],
    min_step_px: float = 25.0,
    min_phase_response: float = 0.04,
    high_anim_mad: float = 0.10,
    tiny_step_px: float = 8.0,
    pose_window_px: Optional[float] = None,
    verbose: bool = True,
) -> List[str]:
    """
    Return a pose-consistent subset of ``frames_paths`` for the stitch pipeline.

    Parameters
    ----------
    frames_paths :
        Sorted list of input frame paths (any order is accepted; the function
        determines the dominant scroll direction from the phase-correlation data).
    min_step_px :
        Minimum camera displacement (full-resolution canvas pixels) between
        consecutive selected frames.  Default 25px.
    min_phase_response :
        Phase-correlation quality threshold.  Pairs below this are rejected
        (motion blur, scene cut, unreliable displacement estimate).
    high_anim_mad :
        MAD threshold for the high-animation / low-movement gate.  Frames
        where the camera barely moved but the thumbnail changed a lot (character
        is animating in place) are discarded.
    tiny_step_px :
        Camera movement threshold below which the high-animation gate is active.
    pose_window_px :
        Width of the pose-consistency lookahead window (canvas pixels).  Defaults
        to the ``ASP_POSE_WINDOW_PX`` env var (80px).  Set to 0 to revert to
        first-past-threshold (v1) behaviour.
    verbose :
        Print diagnostic messages.

    Returns
    -------
    List[str]
        Subset of ``frames_paths`` with near-duplicates, backward-direction
        frames, and pose-inconsistent frames removed.
    """
    N = len(frames_paths)
    if N <= 2:
        return frames_paths

    pw = _POSE_WINDOW_PX if pose_window_px is None else pose_window_px

    # ── 1. Load thumbnails ─────────────────────────────────────────────────
    thumbs = _load_thumbs_parallel(frames_paths)

    # ── 0. §1.64: Exact-duplicate dHash guard ─────────────────────────────
    # Drop consecutive frames whose 64-bit dHash is bit-for-bit identical —
    # MPEG still frames that survived INTER_AREA downscale unchanged.  Runs
    # before all heavier filters so they operate on a deduplicated sequence.
    if _DHASH_EXACT_DROP and N > 2:
        thumbs, frames_paths, _n_dedup_drop = _drop_exact_dhash_duplicates(
            thumbs, frames_paths
        )
        N = len(frames_paths)
        if verbose and _n_dedup_drop > 0:
            print(
                f"  [ExactDedup] §1.64: dropped {_n_dedup_drop} exact-duplicate "
                f"frames → {N} remain"
            )

    # ── 1a. §1.2D: Temporal variance pre-filter ───────────────────────────
    # Drop interior frames whose mean per-pixel variance across the (i-1,i,i+1)
    # triplet is below _TEMPORAL_VAR_THRESH.  Zero camera motion AND zero
    # character animation → frame carries no new canvas information.
    if _TEMPORAL_VAR_THRESH > 0.0 and N > 2:
        thumbs, frames_paths, _n_tvf_drop = _temporal_variance_filter(
            thumbs, frames_paths, _TEMPORAL_VAR_THRESH
        )
        N = len(frames_paths)
        if verbose and _n_tvf_drop > 0:
            print(
                f"  [TemporalVar] Dropped {_n_tvf_drop} static frames "
                f"(thresh={_TEMPORAL_VAR_THRESH:.4f}) → {N} remain"
            )

    # ── 1a-b. §1.2E: Blur/artifact frame pre-rejection ────────────────────
    if _BLUR_REJECT_THRESH > 0.0 and N > 2:
        thumbs, frames_paths, _n_blur_drop = _reject_blurry_frames(
            thumbs, frames_paths, _BLUR_REJECT_THRESH
        )
        N = len(frames_paths)
        if verbose and _n_blur_drop > 0:
            print(
                f"  [BlurReject] Dropped {_n_blur_drop} blurry frames "
                f"(thresh={_BLUR_REJECT_THRESH:.1f}) → {N} remain"
            )

    # ── 1b-a. §1.46: Low-contrast frame pre-rejection ────────────────────
    if _CONTRAST_REJECT_THRESH > 0.0 and N > 2:
        thumbs, frames_paths, _n_contrast_drop = _reject_low_contrast_frames(
            thumbs, frames_paths, _CONTRAST_REJECT_THRESH
        )
        N = len(frames_paths)
        if verbose and _n_contrast_drop > 0:
            print(
                f"  [ContrastReject] Dropped {_n_contrast_drop} low-contrast frames "
                f"(thresh={_CONTRAST_REJECT_THRESH:.1f}) → {N} remain"
            )

    # ── 1b. Hold-block detection (FD-Means preprocessing, §1.11 / §3.4) ───
    # Detect animation "on twos / on threes" hold blocks.  Each block
    # represents one unique character cel.  We record hold_ids[i] so that
    # Pass 2 can prefer candidates from a new hold block (different pose)
    # over candidates within the same hold block (identical pose, zero ARAP
    # benefit).  Hold detection also surfaces the block boundary count as
    # a diagnostic for predicted ARAP workload.
    hold_ids: List[int] = [0] * N  # hold block ID for each frame (0-indexed)
    n_hold_blocks = 1
    _use_dhash_hold = _HOLD_DHASH_THRESHOLD > 0
    if _use_dhash_hold or _HOLD_THRESHOLD > 0.0:
        if _use_dhash_hold:
            hold_reps = _detect_hold_blocks_dhash(
                thumbs, distance_threshold=_HOLD_DHASH_THRESHOLD
            )
            _hd_label = f"dHash(d≤{_HOLD_DHASH_THRESHOLD})"
        else:
            hold_reps = _detect_hold_blocks(thumbs, hold_threshold=_HOLD_THRESHOLD)
            _hd_label = f"MAD(t={_HOLD_THRESHOLD:.3f})"
        _block_id = 0
        _rep_set = set(hold_reps)
        for i in range(N):
            if i in _rep_set and i > 0:
                _block_id += 1
            hold_ids[i] = _block_id
        n_hold_blocks = _block_id + 1
        if verbose:
            print(
                f"  [HoldDetect/{_hd_label}] {n_hold_blocks} hold blocks from {N} frames "
                f"(avg {N / n_hold_blocks:.1f} frames/block)"
            )

    img0 = cv2.imread(frames_paths[0])
    if img0 is not None:
        full_h, full_w = img0.shape[:2]
        th0, tw0 = thumbs[0].shape[:2]
        scale_y = full_h / max(th0, 1)
        scale_x = full_w / max(tw0, 1)
    else:
        scale_y = scale_x = float(_SELECTOR_THUMB_LONG)

    # ── 1c. DINOv2 Features (Pass 2) ───────────────────────────────────────
    dinov2_features = None
    if pw > 0:
        if verbose:
            print("  [SmartSelect] Computing DINOv2 pose features...")
        dinov2_features = _compute_dinov2_features(frames_paths)
        if dinov2_features is not None and verbose:
            print("  [SmartSelect] DINOv2 features loaded successfully.")

    # ── 2. BiRefNet probe masks for camera displacement and pose similarity ──
    _bg_thumb_mask: Optional[np.ndarray] = None  # intersection → stable background
    _fg_thumb_mask: Optional[np.ndarray] = None  # union → character region
    # We need fg mask for pass 2 if DINOv2 failed
    _needs_biref_probes = _TWO_CHANNEL_SELECT or (pw > 0 and dinov2_features is None)
    if _needs_biref_probes:
        try:
            from backend.src.models.wrappers.birefnet_wrapper import (
                BiRefNetWrapper as _BiRefNet,
            )  # §3.14 lazy

            _biref = _BiRefNet()
            _probe_idxs = sorted({0, N // 4, N // 2, 3 * N // 4, N - 1})
            _th_shape = thumbs[0].shape[:2]
            _bg_accum = np.ones(_th_shape, dtype=np.float32)
            _fg_accum = np.zeros(_th_shape, dtype=np.float32)
            _n_ok = 0
            for _pi in _probe_idxs:
                _full = cv2.imread(frames_paths[_pi])
                if _full is None:
                    continue
                _mk = _biref.get_mask(_full)
                _th = thumbs[_pi].shape
                _bg_prob = cv2.resize(
                    (_mk > 127).astype(np.float32),
                    (_th[1], _th[0]),
                    interpolation=cv2.INTER_NEAREST,
                )
                _fg_prob = 1.0 - _bg_prob
                _bg_accum = np.minimum(_bg_accum, _bg_prob)
                _fg_accum = np.maximum(_fg_accum, _fg_prob)
                _n_ok += 1
            with contextlib.suppress(Exception):
                _biref.offload()
            del _biref
            _gc.collect()
            if _torch.cuda.is_available():
                _torch.cuda.empty_cache()
            if _n_ok > 0:
                if _TWO_CHANNEL_SELECT:
                    bg_cov = float(_bg_accum.mean())
                    if verbose:
                        print(
                            f"  [SmartSelect] BiRefNet bg mask: {bg_cov:.0%}, {_n_ok} probes"
                        )
                    _bg_thumb_mask = _bg_accum if bg_cov >= 0.10 else None
                if pw > 0:
                    fg_cov = float(_fg_accum.mean())
                    if verbose:
                        print(
                            f"  [SmartSelect] BiRefNet fg mask: {fg_cov:.0%} fg coverage, "
                            f"{_n_ok} probes"
                        )
                    _fg_thumb_mask = _fg_accum if fg_cov >= 0.05 else None
        except Exception as _e:
            if verbose:
                print(
                    f"  [SmartSelect] BiRefNet unavailable ({_e}); "
                    "using central-crop pose diff"
                )

    # ── 3. Pairwise phase-correlation ──────────────────────────────────────
    raw_dx: List[float] = []
    raw_dy: List[float] = []
    responses: List[float] = []
    frame_mads: List[float] = []

    for i in range(N - 1):
        a = thumbs[i]
        b = thumbs[i + 1]
        th = max(a.shape[0], b.shape[0])
        tw = max(a.shape[1], b.shape[1])
        if a.shape != (th, tw):
            a = np.pad(a, ((0, th - a.shape[0]), (0, tw - a.shape[1])))
        if b.shape != (th, tw):
            b = np.pad(b, ((0, th - b.shape[0]), (0, tw - b.shape[1])))

        # Hold-block skip (§1.11 speedup): within the same hold block,
        # consecutive frames have the same character cel and negligible
        # camera drift.  We zero-out the displacement contribution instead of
        # running phaseCorrelate, reducing correlation pairs from N-1 to K-1
        # (K hold blocks) for typical anime with ~3-frame holds.
        # The MAD is set to 0.0 (identical frames → camera step dominates)
        # so the high_anim_mad gate never misfires on held frames.
        if _HOLD_THRESHOLD > 0.0 and hold_ids[i] == hold_ids[i + 1]:
            raw_dx.append(0.0)
            raw_dy.append(0.0)
            responses.append(1.0)  # treat as perfect correlation (same cel)
            frame_mads.append(0.0)
            continue

        if (
            _CAMFLOW == "bg_masked"
            and _bg_thumb_mask is not None
            and _bg_thumb_mask.shape == a.shape
        ):
            from backend.src.animation.flow.cam_flow import (
                bg_masked_phase_correlate as _bgpc,
            )

            _bg_bool = _bg_thumb_mask > 0.5
            dx_t, dy_t, response = _bgpc(a, b, _bg_bool, _bg_bool)
            _fg = 1.0 - _bg_thumb_mask
            frame_mads.append(float(np.sum(np.abs(b - a) * _fg) / max(_fg.sum(), 1.0)))
        elif _bg_thumb_mask is not None and _bg_thumb_mask.shape == a.shape:
            _m = _bg_thumb_mask
            (dx_t, dy_t), response = cv2.phaseCorrelate(a * _m, b * _m)
            _fg = 1.0 - _m
            frame_mads.append(float(np.sum(np.abs(b - a) * _fg) / max(_fg.sum(), 1.0)))
        elif _OTSU_BG_CORR:
            # §1A: per-pair Otsu bg mask — faster than BiRefNet, per-frame accurate.
            _m = _otsu_bg_mask_pair(a, b)
            if _m is not None and _m.shape == a.shape:
                (dx_t, dy_t), response = cv2.phaseCorrelate(a * _m, b * _m)
                _fg = 1.0 - _m
                frame_mads.append(
                    float(np.sum(np.abs(b - a) * _fg) / max(_fg.sum(), 1.0))
                )
            else:
                (dx_t, dy_t), response = cv2.phaseCorrelate(a, b)
                frame_mads.append(float(np.mean(np.abs(b - a))))
        else:
            (dx_t, dy_t), response = cv2.phaseCorrelate(a, b)
            frame_mads.append(float(np.mean(np.abs(b - a))))
        raw_dx.append(dx_t * scale_x)
        raw_dy.append(dy_t * scale_y)
        responses.append(response)

    # ── 3b. §1.11C: Response-based hold refinement ────────────────────────
    # Pairs where phaseCorrelate response >= _HIGH_HOLD_RESPONSE are near-
    # identical frames (same cel) that MAD-based detection split due to MPEG
    # noise.  Merge their hold blocks now so Pass 2 treats them as one pose.
    if _HOLD_THRESHOLD > 0.0 and _HIGH_HOLD_RESPONSE > 0.0:
        hold_ids, n_hold_blocks = _refine_hold_ids_by_response(
            hold_ids, responses, _HIGH_HOLD_RESPONSE
        )
        if verbose:
            print(
                f"  [HoldRefine] {n_hold_blocks} hold blocks after response refinement"
            )

    # ── 3c. §3.12A: Hold-block sub-pixel averaging ─────────────────────────
    if _HOLD_AVERAGE and _HOLD_THRESHOLD > 0.0:
        thumbs, frames_paths = _hold_block_average(thumbs, hold_ids, frames_paths)
        N = len(thumbs)
        hold_ids = list(range(N))
        if verbose:
            print(f"  [HoldAverage] compressed to {N} hold-averaged frames")

    # ── 4. Dominant scroll axis ────────────────────────────────────────────
    med_dy = float(np.median(raw_dy))
    med_dx = float(np.median(raw_dx))
    if abs(med_dy) >= abs(med_dx):
        axis_steps = raw_dy
        dominant_sign = int(np.sign(med_dy)) if abs(med_dy) > 2.0 else 0
    else:
        axis_steps = raw_dx
        dominant_sign = int(np.sign(med_dx)) if abs(med_dx) > 2.0 else 0

    _chan = "2ch" if _bg_thumb_mask is not None else "1ch"
    if verbose:
        _hold_info = f"  hold_blocks={n_hold_blocks}" if _HOLD_THRESHOLD > 0.0 else ""
        print(
            f"  [SmartSelect] N={N}  axis={'y' if abs(med_dy) >= abs(med_dx) else 'x'}"
            f"  sign={dominant_sign:+d}"
            f"  med_step={abs(med_dy if abs(med_dy) >= abs(med_dx) else med_dx):.1f}px"
            f"  mode={_chan}  pose_window={pw:.0f}px{_hold_info}"
        )

    # ── 5. Pre-compute cumulative canvas positions ─────────────────────────
    cumpos: List[float] = [0.0] * N
    for i in range(N - 1):
        step = axis_steps[i]
        rejected = responses[i] < min_phase_response or (
            abs(step) < tiny_step_px and frame_mads[i] > high_anim_mad
        )
        cumpos[i + 1] = cumpos[i] + (0.0 if rejected else step)

    # ── 6. Pass 1 — v1 greedy selection (first-past-threshold) ───────────────
    selected_v1: List[int] = [0]
    last_pos_v1: float = 0.0

    for i in range(1, N):
        adv = cumpos[i] - last_pos_v1
        nf = adv * dominant_sign if dominant_sign != 0 else abs(adv)
        if nf >= min_step_px:
            selected_v1.append(i)
            last_pos_v1 = cumpos[i]

    if selected_v1[-1] != N - 1:
        selected_v1.append(N - 1)

    # ── 7. Pass 2 — pose-consistent local refinement ──────────────────────
    # For each interior frame, check whether a nearby frame (within ±2 slots,
    # with a minimum/maximum advance constraint) has ≥10% better pose similarity
    # to the previous selected frame.  Frame count is preserved.
    #
    # Similarity metric priority:
    #   1. DINOv2 cosine distance (§3.3): loaded lazily; handles holds natively
    #      because identical-pose frames map to the same point in feature space.
    #   2. fg-masked pixel L1 (_fg_center_diff): falls back to this when DINOv2
    #      weights are unavailable or torch.hub cannot reach HuggingFace.
    _LOOK_RANGE = 2
    _MIN_GAIN = 0.10
    _MIN_ADV_FRAC = 0.50
    _MAX_ADV_FRAC = 2.50

    # Try to compute DINOv2 features when Pass 2 is active.
    _dino_feats: Optional[np.ndarray] = None
    if pw > 0 and len(selected_v1) > 2:
        _dino_feats = _compute_dinov2_features(thumbs)
        if _dino_feats is not None and verbose:
            print(f"  [PoseSelect] DINOv2 features: {_dino_feats.shape} loaded.")
        elif verbose:
            print("  [PoseSelect] DINOv2 unavailable; using fg pixel L1.")

    def _pose_dist(i: int, j: int) -> float:
        """Pose dissimilarity between frame i and frame j (lower = more similar)."""
        if _dino_feats is not None:
            return 1.0 - float(np.dot(_dino_feats[i], _dino_feats[j]))
        return _fg_center_diff(thumbs[i], thumbs[j], _fg_thumb_mask)

    if pw > 0 and len(selected_v1) > 2:
        refined: List[int] = [selected_v1[0]]
        n_subs = 0
        for k in range(1, len(selected_v1) - 1):
            s_prev = refined[-1]
            s_curr = selected_v1[k]
            lo = max(s_prev + 1, s_curr - _LOOK_RANGE)
            hi = min(N - 1, s_curr + _LOOK_RANGE)

            def _valid(c: int) -> bool:
                adv = cumpos[c] - cumpos[s_prev]
                nf = adv * dominant_sign if dominant_sign != 0 else abs(adv)
                return _MIN_ADV_FRAC * min_step_px <= nf <= _MAX_ADV_FRAC * min_step_px

            candidates = [c for c in range(lo, hi + 1) if _valid(c)]
            if not candidates:
                refined.append(s_curr)
                continue
            if dinov2_features is not None:
                last_t = dinov2_features[s_prev]
                curr_score = 1.0 - float(np.dot(last_t, dinov2_features[s_curr]))
                scores = [
                    1.0 - float(np.dot(last_t, dinov2_features[c])) for c in candidates
                ]
            else:
                last_t = thumbs[s_prev]
                curr_score = _fg_center_diff(last_t, thumbs[s_curr], _fg_thumb_mask)
                scores = [
                    _fg_center_diff(last_t, thumbs[c], _fg_thumb_mask)
                    for c in candidates
                ]
            # Hold-block tie-breaking: candidates from the same hold block as
            # s_prev have pose identical to the previous anchor frame.  Their
            # pixel L1 is near-zero not because the pose is good but because
            # the character hasn't moved.  Apply a small penalty to prefer
            # cross-hold candidates.  (DINOv2 handles this naturally — same-hold
            # frames map to the same feature vector — so the penalty is a no-op
            # when DINOv2 is active, but kept for consistency.)
            _SAME_HOLD_PENALTY = 0.05
            scores_adj = [
                s
                + (
                    _SAME_HOLD_PENALTY
                    if _HOLD_THRESHOLD > 0 and hold_ids[c] == hold_ids[s_prev]
                    else 0.0
                )
                for s, c in zip(scores, candidates, strict=False)
            ]
            best_local = int(np.argmin(scores_adj))
            best = candidates[best_local]
            best_score = scores[best_local]
            if best != s_curr and best_score < curr_score * (1.0 - _MIN_GAIN):
                refined.append(best)
                n_subs += 1
                if verbose:
                    print(
                        f"  [PoseSelect] Slot {k}: {s_curr}→{best} "
                        f"(score {curr_score:.3f}→{best_score:.3f})"
                    )
            else:
                refined.append(s_curr)
        refined.append(selected_v1[-1])
        if verbose and n_subs > 0:
            print(f"  [PoseSelect] {n_subs}/{len(selected_v1) - 2} slots refined.")
        selected = refined
    else:
        selected = selected_v1

    if verbose:
        print(
            f"  [SmartSelect] Selected {len(selected)}/{N} frames"
            f"  (dropped {N - len(selected)})."
        )

    # ── 8. §1.2B Near-duplicate luma post-filter ───────────────────────────
    # Drop consecutive selected frames whose mean grayscale diff is below
    # _NEAR_DUP_LUMA (default 0.0 = disabled).  Thumbnail-scale check is
    # sufficient — a 5-luma unit diff at thumbnail scale reliably separates
    # genuine content advance from camera-barely-moved redundancy.
    _sel_paths = [frames_paths[i] for i in selected]
    if _NEAR_DUP_LUMA > 0.0 and len(_sel_paths) > 2:
        _sel_thumbs = [thumbs[i] for i in selected]
        _sel_paths_filt = _near_dup_luma_filter(
            _sel_thumbs, _sel_paths, threshold=_NEAR_DUP_LUMA
        )
        if verbose and len(_sel_paths_filt) < len(_sel_paths):
            print(
                f"  [NearDup] §1.2B: {len(_sel_paths) - len(_sel_paths_filt)} "
                f"near-dup frame(s) dropped (threshold={_NEAR_DUP_LUMA:.1f} luma)."
            )
        _sel_paths = _sel_paths_filt

    return _sel_paths


__all__ = [
    "smart_select_frames",
    "_detect_hold_blocks",
    "_detect_hold_blocks_dhash",
    "_compute_dhash",
    "_drop_exact_dhash_duplicates",
    "_refine_hold_ids_by_response",
    "_temporal_variance_filter",
    "_reject_blurry_frames",
    "_reject_low_contrast_frames",
    "_near_dup_luma_filter",
    "_compute_dinov2_features",
    "_fg_center_diff",
    "_load_thumbs_parallel",
    "_otsu_bg_mask_pair",
    "_hold_block_average",
]
