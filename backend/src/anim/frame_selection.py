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

The pose similarity metric is the L1 distance between the central 50% crops of
two thumbnails.  The central crop de-emphasises the peripheral background (which
changes every frame due to camera motion) and focuses on the character region.

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

# Pose-consistent refinement is disabled by default.  Gradient similarity in
# the central crop is confounded by background structure changes (camera pan
# moves background edges through the frame), causing wrong frame choices on
# tests with complex backgrounds.  Enable via ASP_POSE_WINDOW_PX=80 for
# experimentation.  Proper implementation requires a pose estimation model.
try:
    _POSE_WINDOW_PX = float(os.environ.get("ASP_POSE_WINDOW_PX", "0"))
except ValueError:
    _POSE_WINDOW_PX = 0.0

# Two-channel selection using BiRefNet background masks for cleaner camera
# displacement estimates.  Disabled by default — BiRefNet overhead is significant
# and the approach changed frame timing in ways that hurt GT-SSIM.
_TWO_CHANNEL_SELECT = os.environ.get("ASP_TWO_CHANNEL_SELECT", "0") != "0"
_PERIPH_BORDER_FRAC = 0.24


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


def _load_thumbs_parallel(frames_paths: List[str], max_workers: int = 8) -> List[np.ndarray]:
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
    Gradient-magnitude L1 between two thumbnails, optionally weighted by a
    foreground probability mask.

    When fg_mask is provided (BiRefNet fg probability map at thumbnail scale),
    background pixels receive near-zero weight so that locker/wall/scenery
    edges that change as the camera pans cannot dominate the comparison.  Only
    the character's silhouette and limb outlines drive the score — frames with
    the same character pose score low; different poses score high.

    Without fg_mask, falls back to central-crop gradient diff, which is partly
    confounded by background structure.

    Returns a non-negative float (0 = identical character structure).
    """
    h = min(thumb_a.shape[0], thumb_b.shape[0])
    w = min(thumb_a.shape[1], thumb_b.shape[1])

    def _grad_mag(img: np.ndarray) -> np.ndarray:
        gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
        return np.sqrt(gx * gx + gy * gy)

    if fg_mask is not None and fg_mask.shape[0] >= h and fg_mask.shape[1] >= w:
        a = thumb_a[:h, :w]
        b = thumb_b[:h, :w]
        mask = fg_mask[:h, :w]
        diff = np.abs(_grad_mag(a) - _grad_mag(b))
        total_weight = float(mask.sum())
        if total_weight >= 10.0:
            return float(np.dot(diff.ravel(), mask.ravel()) / total_weight)
        # fg mask too sparse — fall through to central-crop

    # Fallback: central 50% crop
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
                        print(f"  [SmartSelect] BiRefNet bg mask: {bg_cov:.0%}, {_n_ok} probes")
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
        raw_dx.append(float(dx_t) * scale_x)
        raw_dy.append(float(dy_t) * scale_y)
        responses.append(float(response))

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
        print(
            f"  [SmartSelect] N={N}  axis={'y' if abs(med_dy) >= abs(med_dx) else 'x'}"
            f"  sign={dominant_sign:+d}"
            f"  med_step={abs(med_dy if abs(med_dy) >= abs(med_dx) else med_dx):.1f}px"
            f"  mode={_chan}  pose_window={pw:.0f}px"
        )

    # ── 5. Pre-compute cumulative canvas positions ─────────────────────────
    cumpos: List[float] = [0.0] * N
    for i in range(N - 1):
        step = axis_steps[i]
        rejected = (
            responses[i] < min_phase_response
            or (abs(step) < tiny_step_px and frame_mads[i] > high_anim_mad)
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
    # with a minimum/maximum advance constraint) has ≥10% better gradient
    # similarity to the previous selected frame.  Frame count is preserved.
    _LOOK_RANGE = 2
    _MIN_GAIN = 0.10
    _MIN_ADV_FRAC = 0.50
    _MAX_ADV_FRAC = 2.50

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
            last_t = thumbs[s_prev]
            curr_score = _fg_center_diff(last_t, thumbs[s_curr], _fg_thumb_mask)
            scores = [_fg_center_diff(last_t, thumbs[c], _fg_thumb_mask) for c in candidates]
            best_local = int(np.argmin(scores))
            best = candidates[best_local]
            best_score = scores[best_local]
            if best != s_curr and best_score < curr_score * (1.0 - _MIN_GAIN):
                refined.append(best)
                n_subs += 1
                if verbose:
                    print(
                        f"  [PoseSelect] Slot {k}: {s_curr}→{best} "
                        f"(grad {curr_score:.3f}→{best_score:.3f})"
                    )
            else:
                refined.append(s_curr)
        refined.append(selected_v1[-1])
        if verbose and n_subs > 0:
            print(f"  [PoseSelect] {n_subs}/{len(selected_v1)-2} slots refined.")
        selected = refined
    else:
        selected = selected_v1

    if verbose:
        print(
            f"  [SmartSelect] Selected {len(selected)}/{N} frames"
            f"  (dropped {N - len(selected)})."
        )
    return [frames_paths[i] for i in selected]


__all__ = ["smart_select_frames", "_fg_center_diff", "_load_thumbs_parallel"]
