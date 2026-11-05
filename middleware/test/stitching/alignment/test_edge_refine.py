"""Sub-pixel edge refinement (EfficientLoFTR's ~16 px grid, 2026-11-04)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from middleware.src.stitching.alignment.matching._refine import (
    refine_translation,
    sift_translation,
)

H, W = 360, 640


def _scene(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    big = rng.integers(0, 255, (H * 2, W * 2, 3), dtype=np.uint8)
    big = cv2.GaussianBlur(big, (0, 0), 2.5)
    return cv2.normalize(big, None, 0, 255, cv2.NORM_MINMAX)


def _pair(t: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    """Frame j sees the scene shifted so that p_j = p_i + t."""
    s = _scene()
    A = np.float32([[1, 0, -200], [0, 1, -150]])
    B = np.float32([[1, 0, -200 + t[0]], [0, 1, -150 + t[1]]])
    fi = cv2.warpAffine(s, A, (W, H), flags=cv2.INTER_LINEAR)
    fj = cv2.warpAffine(s, B, (W, H), flags=cv2.INTER_LINEAR)
    return fi, fj


@pytest.mark.parametrize("truth", [(0.0, 37.4), (-12.6, 61.3), (5.25, -22.75)])
def test_refines_quantised_candidate(truth):
    fi, fj = _pair(truth)
    coarse = (round(truth[0] / 16) * 16.0, round(truth[1] / 16) * 16.0)
    r = refine_translation(fi, fj, None, None, [coarse], use_sift=False)
    assert r is not None
    assert abs(r[0] - truth[0]) < 0.3 and abs(r[1] - truth[1]) < 0.3
    assert r[2] > 0.9


def test_sift_hypothesis_rescues_a_zero_candidate():
    truth = (3.0, 74.0)  # the asp_test27 class: matcher said 0, frame moved 74
    fi, fj = _pair(truth)
    st = sift_translation(fi, fj, None, None)
    assert st is not None and abs(st[1] - truth[1]) < 2
    r = refine_translation(fi, fj, None, None, [(0.0, 0.0)])
    assert r is not None and abs(r[1] - truth[1]) < 0.3


def test_background_mask_ignores_a_moving_foreground():
    truth = (0.0, 40.0)
    fi, fj = _pair(truth)
    # A foreground block that stays put (character holding still on screen).
    fi[100:260, 200:440] = (30, 200, 30)
    fj[100:260, 200:440] = (30, 200, 30)
    mask = np.full((H, W), 255, np.uint8)
    mask[90:270, 190:450] = 0
    r = refine_translation(fi, fj, mask, mask, [(0.0, 32.0)], use_sift=False)
    assert r is not None and abs(r[1] - truth[1]) < 0.5


def test_unrelated_frames_return_none():
    a = _scene(1)[:H, :W]
    b = _scene(2)[:H, :W]
    assert refine_translation(a, b, None, None, [(0.0, 0.0)], use_sift=False) is None
