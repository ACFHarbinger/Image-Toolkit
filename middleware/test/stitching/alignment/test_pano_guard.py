"""OpenCV Stitcher canvas-size preflight (asp_test12 PANORAMA OOM)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from middleware.src.stitching.alignment.canvas import (
    PANO_TOO_LARGE,
    _pano_size_ok,
    _predicted_pano_size,
    _try_opencv_stitch,
)


def _tiles() -> list[np.ndarray]:
    rng = np.random.default_rng(0)
    scene = cv2.GaussianBlur(rng.integers(0, 255, (400, 1200, 3), dtype=np.uint8), (0, 0), 3)
    scene = cv2.normalize(scene, None, 0, 255, cv2.NORM_MINMAX)
    return [np.ascontiguousarray(scene[:, x : x + 500]) for x in (0, 350, 700)]


@pytest.mark.parametrize("mode", [0, 1])
def test_prediction_matches_compose(mode):
    cv2.ocl.setUseOpenCL(False)
    frames = _tiles()
    st = cv2.Stitcher_create(mode)
    st.setRegistrationResol(0.6)
    assert st.estimateTransform(frames) == cv2.Stitcher_OK
    pred = _predicted_pano_size(st, frames, mode)
    status, pano = st.composePanorama()
    assert status == cv2.Stitcher_OK
    assert pred == (pano.shape[1], pano.shape[0])


def test_size_limits(monkeypatch):
    frames = [np.zeros((1080, 1920, 3), np.uint8)] * 12
    assert _pano_size_ok((1920, 1200), frames)
    assert not _pano_size_ok((44574, 22292), frames)  # asp_test05 PANORAMA
    assert not _pano_size_ok((40000, 600), frames)  # past CANVAS_MAX_DIM
    assert not _pano_size_ok((0, 0), frames)
    monkeypatch.setenv("ASP_PANORAMA_MAX_AREA_RATIO", "0.01")
    assert not _pano_size_ok((1920, 1200), frames)


def test_oversized_attempt_is_refused(monkeypatch):
    monkeypatch.setenv("ASP_PANORAMA_MAX_AREA_RATIO", "0.01")
    status, pano = _try_opencv_stitch(_tiles(), 1, 0.6)
    assert status == PANO_TOO_LARGE and pano is None
