"""Per-stage registration routing (2026-11-05)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from middleware.src.stitching.core.pipeline.registration_router import (
    SOURCE_ASP,
    SOURCE_OPENCV,
    PoseCandidate,
    _camera_forward,
    choose,
    opencv_scans_registration,
    pose_consistency,
)

H, W = 270, 480
STEP = 60


def _strip(n: int) -> list[np.ndarray]:
    """n frames of a vertical pan over a textured scene, STEP px per frame."""
    rng = np.random.default_rng(3)
    big = rng.integers(0, 255, (H + STEP * n, W, 3), dtype=np.uint8)
    big = cv2.GaussianBlur(big, (0, 0), 2.0)
    big = cv2.normalize(big, None, 0, 255, cv2.NORM_MINMAX)
    return [big[k * STEP : k * STEP + H].copy() for k in range(n)]


def _true_affines(n: int) -> list[np.ndarray]:
    return [np.float32([[1, 0, 0], [0, 1, k * STEP]]) for k in range(n)]


def _cand(source, affines, frames):
    ctx = {"frames": frames, "scans_frames": frames, "bg_masks": [None] * len(frames),
           "image_paths": [f"f{i}.png" for i in range(len(frames))]}
    return PoseCandidate.subset(source, affines, list(range(len(frames))), ctx)


def test_consistency_prefers_true_poses():
    fr = _strip(5)
    good = pose_consistency(fr, [None] * 5, _true_affines(5))
    bad_aff = _true_affines(5)
    bad_aff[3] = np.float32([[1, 0, 25], [0, 1, 3 * STEP - 40]])
    bad = pose_consistency(fr, [None] * 5, bad_aff)
    assert good["mean"] < 0.01
    assert bad["mean"] > 2 * good["mean"]


def test_missing_overlap_is_penalised():
    fr = _strip(3)
    far = _true_affines(3)
    far[2] = np.float32([[1, 0, 0], [0, 1, 5000]])
    s = pose_consistency(fr, [None] * 3, far)
    assert s["misses"] == 1 and s["mean"] > 0.1


def test_camera_forward_is_translation_for_identity_rotation():
    R = np.array([[1, 0, -10], [0, 1, -20], [0, 0, 1]], np.float64)
    A = _camera_forward(R, work_scale=0.5)
    np.testing.assert_allclose(A, [[1, 0, 20], [0, 1, 40]], atol=1e-6)


def test_opencv_registration_recovers_the_pan():
    fr = _strip(5)
    got = opencv_scans_registration(fr)
    assert got is not None
    fwd, idx, _ = got
    assert idx == sorted(idx) and len(idx) >= 4
    ty = [float(fwd[k][1, 2]) for k in range(len(idx))]
    steps = np.diff(ty) / np.diff(idx)
    np.testing.assert_allclose(steps, STEP, atol=2.0)


@pytest.mark.parametrize(
    ("mode", "expected"), [("asp", SOURCE_ASP), ("opencv", SOURCE_OPENCV)]
)
def test_forced_modes(mode, expected):
    fr = _strip(4)
    cands = [_cand(SOURCE_ASP, _true_affines(4), fr), _cand(SOURCE_OPENCV, _true_affines(4), fr)]
    pick, tele = choose(cands, 4, mode)
    assert pick.source == expected and tele["selected"] == expected


def test_auto_keeps_opencv_unless_asp_is_clearly_better():
    fr = _strip(4)
    same = [_cand(SOURCE_ASP, _true_affines(4), fr), _cand(SOURCE_OPENCV, _true_affines(4), fr)]
    assert choose(same, 4, "auto")[0].source == SOURCE_OPENCV
    off = _true_affines(4)
    off[2] = np.float32([[1, 0, 30], [0, 1, 2 * STEP - 35]])
    better_asp = [_cand(SOURCE_ASP, _true_affines(4), fr), _cand(SOURCE_OPENCV, off, fr)]
    pick, tele = choose(better_asp, 4, "auto")
    assert pick.source == SOURCE_ASP and tele["reason"] == "asp_more_consistent"


def test_auto_prefers_asp_when_opencv_drops_most_frames():
    fr = _strip(6)
    cv = _cand(SOURCE_OPENCV, _true_affines(2), fr[:2])
    asp = _cand(SOURCE_ASP, _true_affines(6), fr)
    pick, tele = choose([asp, cv], 6, "auto")
    assert pick.source == SOURCE_ASP and tele["reason"] == "opencv_dropped_frames"


def test_single_candidate():
    fr = _strip(3)
    pick, tele = choose([_cand(SOURCE_OPENCV, _true_affines(3), fr)], 3, "asp")
    assert pick.source == SOURCE_OPENCV and tele["reason"] == "only_candidate"
