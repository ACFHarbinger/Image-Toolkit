"""Per-stage routing for registration (2026-11-05).

ASP used to hand a whole sequence to OpenCV (SCANS / PANORAMA output
returned as-is) whenever one of its gates failed. Now only the
registration stage is routed: OpenCV SCANS registration is one pose
source, ASP's matcher + bundle adjustment the other, and whichever is
chosen feeds the same ASP refine / render / trim / crop stages.

``ASP_REGISTRATION``:
  ``auto``   (default) compare both by background overlap consistency
  ``opencv`` OpenCV poses when estimation succeeds, else ASP's
  ``asp``    ASP's poses when they pass the health gate, else OpenCV's

Poses are forward ``frame -> canvas`` 2x3 affines (ASP's convention).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import cv2
import numpy as np

logger = logging.getLogger(__name__)

SOURCE_ASP = "asp"
SOURCE_OPENCV = "opencv_scans"

# Consistency is measured at this scale of the frame.
_SCORE_SCALE = 0.25
# An adjacent pair overlapping less than this (frame-area share) is a miss.
_MIN_PAIR_OVERLAP = 0.05
# Error charged for a missing overlap (mean |Δ| on 0..1 gray is ~0.01-0.04
# when aligned, ~0.08-0.2 when not).
_MISS_PENALTY = 0.25
# auto: ASP replaces OpenCV only when its error is this much lower.
_ASP_MARGIN = float(os.environ.get("ASP_REGISTRATION_ASP_MARGIN", "0.15"))
# auto: OpenCV keeping less than this share of frames is not preferred.
_MIN_KEPT_FRAC = 0.6


def registration_mode() -> str:
    mode = os.environ.get("ASP_REGISTRATION", "auto").strip().lower()
    return mode if mode in ("auto", "opencv", "asp") else "auto"


@dataclass
class PoseCandidate:
    """A pose set and the frame lists it applies to (one entry per frame)."""

    source: str
    affines: list[np.ndarray]
    frames: list[np.ndarray]  # photometrically corrected
    scans_frames: list[np.ndarray]  # raw (seam renderer, consistency score)
    bg_masks: list[np.ndarray | None]
    image_paths: list[str]
    detail: dict = field(default_factory=dict)
    score: dict | None = None

    @classmethod
    def subset(cls, source, affines, idx, ctx: dict, detail=None) -> PoseCandidate:
        """Candidate over ``idx`` of the lists in ``ctx`` (frames,
        scans_frames, bg_masks, image_paths)."""
        sf = ctx["scans_frames"] or ctx["frames"]
        return cls(
            source,
            [np.asarray(a, np.float32).copy() for a in affines],
            [ctx["frames"][i] for i in idx],
            [sf[i] for i in idx],
            [ctx["bg_masks"][i] for i in idx],
            [ctx["image_paths"][i] for i in idx],
            dict(detail or {}),
        )



def _camera_forward(R, work_scale: float) -> np.ndarray:
    """Frame -> pano affine of a SCANS camera at full resolution.

    AffineWarper turns camera ``[A|t]`` into ``R = A^T``, ``T = -A^T t``, and
    composePanorama scales T by 1/workScale, so the forward map is
    ``p -> A^T p - A^T t / workScale`` (verified against composePanorama by
    the contrast harness's replica, 2026-11-03).
    """
    H = np.asarray(R, np.float64)
    At = H[:2, :2].T
    return np.hstack([At, (-At @ H[:2, 2] / work_scale)[:, None]]).astype(np.float32)


def opencv_scans_registration(
    frames: list[np.ndarray],
    bg_masks: list[np.ndarray | None] | None = None,
    tries: int | None = None,
) -> tuple[list[np.ndarray], list[int], dict] | None:
    """OpenCV SCANS registration (the fallback's retry ladder, SCANS only):
    (forward affines, component frame indices in temporal order, detail).

    OpenCV's RANSAC draws from a shared RNG, so one estimate on the same
    frames can be badly wrong (asp_test04 2026-11-05: 1 of 5 draws put a
    frame at 2.7x scale, 3000 px off; ASP got that draw, the bench's OpenCV
    run a good one). The first ladder step that succeeds is drawn ``tries``
    times with fixed seeds and the most consistent pose set is kept.
    """
    from middleware.src.stitching.alignment.canvas import (
        _guarded_stitcher,
        _scan_stitch_attempts,
    )

    if tries is None:
        tries = max(1, int(os.environ.get("ASP_OPENCV_REG_TRIES", "3")))
    masks = bg_masks if bg_masks is not None and len(bg_masks) == len(frames) else [None] * len(frames)
    for name, idx, mode, resol in _scan_stitch_attempts(len(frames)):
        if mode != 1:
            continue
        draws = []
        for seed in range(tries):
            cv2.setRNGSeed(seed)
            try:
                status, stitcher = _guarded_stitcher([frames[i] for i in idx], mode, resol)
            except cv2.error as exc:
                logger.info("[Stitch]   OpenCV registration %s raised %s", name, exc)
                continue
            logger.info(
                "[Stitch]   OpenCV registration %s seed=%d n=%d status=%s", name, seed, len(idx), status
            )
            if stitcher is None:
                continue
            comp = [idx[int(c)] for c in np.asarray(stitcher.component()).ravel()]
            cams = stitcher.cameras()
            if len(comp) < 2 or len(cams) != len(comp):
                continue
            fwd = [_camera_forward(c.R, stitcher.workScale()) for c in cams]
            order = np.argsort(comp)  # keep temporal order
            fwd, comp = [fwd[k] for k in order], [comp[k] for k in order]
            score = pose_consistency([frames[i] for i in comp], [masks[i] for i in comp], fwd)
            # A draw that keeps more frames covers more; misses already cost.
            draws.append((score["mean"] - 0.001 * len(comp), seed, fwd, comp, score))
        if draws:
            _, seed, fwd, comp, score = min(draws, key=lambda d: d[0])
            return fwd, comp, {
                "attempt": name,
                "registration_resol": resol,
                "n_input": len(frames),
                "seed": seed,
                "draws": [{"seed": d[1], "n": len(d[3]), "mean": d[4]["mean"]} for d in draws],
            }
    return None


def _to3(A: np.ndarray) -> np.ndarray:
    return np.vstack([np.asarray(A, np.float64)[:2], [0.0, 0.0, 1.0]])


def pose_consistency(
    frames: list[np.ndarray],
    bg_masks: list[np.ndarray | None],
    affines: list[np.ndarray],
) -> dict:
    """Mean |Δgray| (0..1) over the background overlap of temporally
    adjacent frames under ``affines``; a missing overlap costs
    ``_MISS_PENALTY``. Lower is better."""
    s = _SCORE_SCALE
    S = np.diag([s, s, 1.0])
    Sinv = np.diag([1 / s, 1 / s, 1.0])
    errs: list[float] = []
    misses = 0
    for i in range(len(frames) - 1):
        a, b = frames[i], frames[i + 1]
        ga = cv2.resize(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        gb = cv2.resize(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        h, w = ga.shape
        # frame b pixel -> canvas -> frame a pixel, at scale s
        M = (S @ np.linalg.inv(_to3(affines[i])) @ _to3(affines[i + 1]) @ Sinv)[:2].astype(np.float32)
        wb = cv2.warpAffine(gb, M, (w, h), flags=cv2.INTER_LINEAR)
        inside = cv2.warpAffine(np.ones_like(gb), M, (w, h), flags=cv2.INTER_NEAREST) > 0
        if inside.mean() < _MIN_PAIR_OVERLAP:
            errs.append(_MISS_PENALTY)
            misses += 1
            continue
        valid = inside.copy()
        ma, mb = bg_masks[i] if i < len(bg_masks) else None, bg_masks[i + 1] if i + 1 < len(bg_masks) else None
        if ma is not None and mb is not None:
            ba = cv2.resize(ma, (w, h), interpolation=cv2.INTER_NEAREST) > 127
            bb = cv2.warpAffine(
                cv2.resize(mb, (gb.shape[1], gb.shape[0]), interpolation=cv2.INTER_NEAREST),
                M, (w, h), flags=cv2.INTER_NEAREST,
            ) > 127
            bgv = valid & ba & bb
            if bgv.sum() >= 0.2 * valid.sum():  # masks can call most of a cel "fg"
                valid = bgv
        d = np.abs(ga.astype(np.float32) - wb.astype(np.float32))[valid]
        errs.append(float(d.mean() / 255.0) if d.size else _MISS_PENALTY)
    if not errs:
        return {"mean": _MISS_PENALTY, "median": _MISS_PENALTY, "pairs": 0, "misses": 0}
    return {
        "mean": round(float(np.mean(errs)), 5),
        "median": round(float(np.median(errs)), 5),
        "pairs": len(errs),
        "misses": misses,
    }


def choose(
    candidates: list[PoseCandidate],
    n_frames: int,
    mode: str | None = None,
) -> tuple[PoseCandidate | None, dict]:
    """Pick the registration for the run. ``n_frames``: frames ASP had going
    into registration. Returns (candidate, telemetry)."""
    mode = mode or registration_mode()
    by = {c.source: c for c in candidates}
    for c in candidates:
        if c.score is None:
            c.score = pose_consistency(c.scans_frames, c.bg_masks, c.affines)
    tele = {
        "mode": mode,
        "candidates": {
            c.source: {
                "n_frames": len(c.affines),
                "kept_frac": round(len(c.affines) / max(1, n_frames), 3),
                "score": c.score,
                **c.detail,
            }
            for c in candidates
        },
    }
    asp, cv = by.get(SOURCE_ASP), by.get(SOURCE_OPENCV)
    if asp is None or cv is None:
        pick = asp or cv
        tele["reason"] = "only_candidate" if pick else "no_candidate"
    elif mode == "asp":
        pick, tele["reason"] = asp, "mode_asp"
    elif mode == "opencv":
        pick, tele["reason"] = cv, "mode_opencv"
    elif len(cv.affines) < _MIN_KEPT_FRAC * n_frames <= len(asp.affines):
        pick, tele["reason"] = asp, "opencv_dropped_frames"
    elif len(asp.affines) < _MIN_KEPT_FRAC * n_frames <= len(cv.affines):
        # spatial dedup on bad edges (asp_test95: 37 -> 3 frames)
        pick, tele["reason"] = cv, "asp_dropped_frames"
    elif asp.score["mean"] < (1.0 - _ASP_MARGIN) * cv.score["mean"]:
        pick, tele["reason"] = asp, "asp_more_consistent"
    else:
        pick, tele["reason"] = cv, "opencv_default"
    tele["selected"] = pick.source if pick else None
    return pick, tele


__all__ = [
    "PoseCandidate",
    "SOURCE_ASP",
    "SOURCE_OPENCV",
    "choose",
    "opencv_scans_registration",
    "pose_consistency",
    "registration_mode",
]
