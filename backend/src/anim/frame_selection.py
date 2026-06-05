"""
backend/src/anim/frame_selection.py
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
import os
from typing import List, Optional

import cv2
import numpy as np

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

# Animation hold detection — FD-Means preprocessing (§1.11 / §3.4).
# Set ASP_HOLD_THRESHOLD to a positive float (e.g. "0.025") to enable.
# A value of 0.0 (default) disables hold detection entirely.
try:
    _HOLD_THRESHOLD = float(os.environ.get("ASP_HOLD_THRESHOLD", "0.0"))
except ValueError:
    _HOLD_THRESHOLD = 0.0

# DINOv2 frame feature cache (§3.3).  Populated lazily on first call to
# _compute_dinov2_features(); keyed by model name string.
_DINOV2_CACHE: dict = {}


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

    blocks: List[int] = [0]
    for i in range(1, N):
        h = min(thumbs[i].shape[0], thumbs[i - 1].shape[0])
        w = min(thumbs[i].shape[1], thumbs[i - 1].shape[1])
        mad = float(np.mean(np.abs(
            thumbs[i][:h, :w].astype(np.float32)
            - thumbs[i - 1][:h, :w].astype(np.float32)
        )))
        if mad > hold_threshold:
            blocks.append(i)

    return blocks


# ---------------------------------------------------------------------------
# DINOv2 submodular feature extraction (§3.3)
# ---------------------------------------------------------------------------


def _compute_dinov2_features(
    thumbs: List[np.ndarray],
    device: Optional[str] = None,
    thumb_size: int = 224,
    batch_size: int = 16,
) -> "Optional[np.ndarray]":
    """
    Extract DINOv2-ViT-S/14 patch tokens from grayscale thumbnails.

    Returns (N, 384) float32 L2-normalised feature matrix, or None if
    ``torch`` / ``torchvision`` or the DINOv2 weights are unavailable.

    Features are extracted from the [CLS] token of ``dinov2_vits14``.  Because
    DINOv2 was trained with self-supervised patch-level objectives rather than
    class labels, its [CLS] token encodes holistic image appearance including
    pose and style — making it a far better pose-similarity signal than pixel
    L1, especially for cel-shaded anime where colour gradients are near-zero
    (defeating gradient-based metrics) but structural differences are large.

    The facility-location coverage objective used in Pass 2 selects frames that
    maximise the DINOv2 cosine diversity of the selected set, guaranteeing that
    animation holds are not double-counted: identical-pose frames collapse to
    the same point in feature space and only one representative is chosen.
    """
    try:
        import torch
        import torchvision.transforms.functional as TF
    except ImportError:
        return None

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model_key = f"dinov2_vits14_{device}"
    if model_key not in _DINOV2_CACHE:
        try:
            model = torch.hub.load(
                "facebookresearch/dinov2", "dinov2_vits14", verbose=False
            )
            model.eval().to(device)
            _DINOV2_CACHE[model_key] = model
        except Exception:
            _DINOV2_CACHE[model_key] = None

    model = _DINOV2_CACHE.get(model_key)
    if model is None:
        return None

    import torch

    all_feats: "List[np.ndarray]" = []
    mean = [0.485, 0.456, 0.406]
    std = [0.229, 0.224, 0.225]

    try:
        for start in range(0, len(thumbs), batch_size):
            batch_imgs = thumbs[start : start + batch_size]
            tensors = []
            for gray in batch_imgs:
                # Resize to thumb_size × thumb_size, convert gray → RGB
                resized = cv2.resize(gray, (thumb_size, thumb_size))
                rgb = np.stack([resized, resized, resized], axis=2)  # (H,W,3) float32
                t = torch.from_numpy(rgb).permute(2, 0, 1).float()  # (3,H,W)
                for c in range(3):
                    t[c] = (t[c] - mean[c]) / std[c]
                tensors.append(t)
            batch_t = torch.stack(tensors, dim=0).to(device)  # (B,3,H,W)
            with torch.no_grad():
                feats = model(batch_t)  # (B, 384)
            feats_np = feats.cpu().numpy().astype(np.float32)
            # L2 normalise each row
            norms = np.linalg.norm(feats_np, axis=1, keepdims=True).clip(min=1e-8)
            all_feats.append(feats_np / norms)
    except Exception:
        return None

    return np.concatenate(all_feats, axis=0)  # (N, 384)


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

    # ── 1b. Hold-block detection (FD-Means preprocessing, §1.11 / §3.4) ───
    # Detect animation "on twos / on threes" hold blocks.  Each block
    # represents one unique character cel.  We record hold_ids[i] so that
    # Pass 2 can prefer candidates from a new hold block (different pose)
    # over candidates within the same hold block (identical pose, zero ARAP
    # benefit).  Hold detection also surfaces the block boundary count as
    # a diagnostic for predicted ARAP workload.
    hold_ids: List[int] = [0] * N  # hold block ID for each frame (0-indexed)
    n_hold_blocks = 1
    if _HOLD_THRESHOLD > 0.0:
        hold_reps = _detect_hold_blocks(thumbs, hold_threshold=_HOLD_THRESHOLD)
        _block_id = 0
        _rep_set = set(hold_reps)
        for i in range(N):
            if i in _rep_set and i > 0:
                _block_id += 1
            hold_ids[i] = _block_id
        n_hold_blocks = _block_id + 1
        if verbose:
            print(
                f"  [HoldDetect] {n_hold_blocks} hold blocks from {N} frames "
                f"(avg {N / n_hold_blocks:.1f} frames/block, "
                f"threshold={_HOLD_THRESHOLD:.3f})"
            )

    img0 = cv2.imread(frames_paths[0])
    if img0 is not None:
        full_h, full_w = img0.shape[:2]
        th0, tw0 = thumbs[0].shape[:2]
        scale_y = full_h / max(th0, 1)
        scale_x = full_w / max(tw0, 1)
    else:
        scale_y = scale_x = float(_SELECTOR_THUMB_LONG)

    # ── 2. BiRefNet probe masks for camera displacement and pose similarity ──
    _bg_thumb_mask: Optional[np.ndarray] = None  # intersection → stable background
    _fg_thumb_mask: Optional[np.ndarray] = None  # union → character region
    _needs_biref_probes = _TWO_CHANNEL_SELECT or pw > 0
    if _needs_biref_probes:
        try:
            from backend.src.models.birefnet_wrapper import BiRefNetWrapper
            import gc as _gc
            import torch as _torch

            _biref = BiRefNetWrapper()
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
            try:
                _biref.offload()
            except Exception:
                pass
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

        if _bg_thumb_mask is not None and _bg_thumb_mask.shape == a.shape:
            _m = _bg_thumb_mask
            (dx_t, dy_t), response = cv2.phaseCorrelate(a * _m, b * _m)
            _fg = 1.0 - _m
            frame_mads.append(float(np.sum(np.abs(b - a) * _fg) / max(_fg.sum(), 1.0)))
        else:
            (dx_t, dy_t), response = cv2.phaseCorrelate(a, b)
            frame_mads.append(float(np.mean(np.abs(b - a))))
        raw_dx.append(dx_t * scale_x)
        raw_dy.append(dy_t * scale_y)
        responses.append(response)

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
            return float(1.0 - float(np.dot(_dino_feats[i], _dino_feats[j])))
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
            curr_score = _pose_dist(s_prev, s_curr)
            scores = [_pose_dist(s_prev, c) for c in candidates]
            # Hold-block tie-breaking: candidates from the same hold block as
            # s_prev have pose identical to the previous anchor frame.  Their
            # pixel L1 is near-zero not because the pose is good but because
            # the character hasn't moved.  Apply a small penalty to prefer
            # cross-hold candidates.  (DINOv2 handles this naturally — same-hold
            # frames map to the same feature vector — so the penalty is a no-op
            # when DINOv2 is active, but kept for consistency.)
            _SAME_HOLD_PENALTY = 0.05
            scores_adj = [
                s + (_SAME_HOLD_PENALTY if _HOLD_THRESHOLD > 0 and hold_ids[c] == hold_ids[s_prev] else 0.0)
                for s, c in zip(scores, candidates)
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
    return [frames_paths[i] for i in selected]


__all__ = [
    "smart_select_frames",
    "_detect_hold_blocks",
    "_compute_dinov2_features",
    "_fg_center_diff",
    "_load_thumbs_parallel",
]
