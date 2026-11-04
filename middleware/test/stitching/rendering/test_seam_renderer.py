"""Seam renderer (graph-cut seams + multiband, the SCANS composer)."""

from __future__ import annotations

import numpy as np
from middleware.src.stitching.rendering.rendering import _render, _render_seam


def _scene(h: int = 600, w: int = 320, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, (h // 20, w // 20, 3), dtype=np.uint8)
    return np.kron(base, np.ones((20, 20, 1), np.uint8))


def _crops(scene: np.ndarray, fh: int, step: int, n: int):
    frames, affines = [], []
    for k in range(n):
        y = k * step
        frames.append(scene[y : y + fh].copy())
        affines.append(np.array([[1.0, 0, 0], [0, 1.0, y]], np.float64))
    return frames, affines


def test_vertical_scroll_reconstructs_scene():
    scene = _scene()
    frames, affines = _crops(scene, 240, 120, 4)
    canvas, valid = _render_seam(frames, affines, 600, 320)
    assert canvas.shape == (600, 320, 3) and canvas.dtype == np.uint8
    assert (valid[:600] == 255).all()
    # Consistent frames: the blend must reproduce the scene (block edges aside).
    err = np.abs(canvas.astype(int) - scene.astype(int)).mean()
    assert err < 3.0, err


def test_seam_avoids_inconsistent_region():
    scene = _scene()
    frames, affines = _crops(scene, 360, 240, 2)  # overlap rows 240..360
    # Frame 1 differs in the top half of the overlap (moving content).
    frames[1][0:60] = 255 - frames[1][0:60]
    canvas, _ = _render_seam(frames, affines, 600, 320)
    region = canvas[250:290].astype(int)
    assert np.abs(region - scene[250:290].astype(int)).mean() < 10.0


def test_valid_mask_and_black_outside():
    scene = _scene()
    frames, affines = _crops(scene, 200, 100, 2)  # covers rows 0..300
    canvas, valid = _render_seam(frames, affines, 400, 320)
    assert (valid[:300] == 255).all() and (valid[300:] == 0).all()
    assert canvas[300:].max() == 0


def test_single_frame_and_dispatch():
    scene = _scene()
    frames, affines = _crops(scene, 200, 0, 1)
    canvas, valid = _render_seam(frames, affines, 200, 320)
    assert np.array_equal(canvas, scene[:200])
    c, v, wc, wf = _render(frames, affines, [None], 200, 320, renderer="seam")
    assert np.array_equal(c, canvas) and wc == [] and wf == []


def test_tilted_frames_leave_no_invalid_pixels():
    # A tilted, fractional-t frame leaves zeros at its ROI edges; the union of
    # frames must still be valid there (regression: black lines at seams).
    scene = _scene()
    frames, affines = _crops(scene, 240, 120, 4)
    th = np.deg2rad(0.3)  # slight tilt: each ROI gets a zero wedge at its edges
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    for k, A in enumerate(affines):
        A[:, :2] = R
        A[0, 2] += 4 + 0.4 * (k % 2)
        A[1, 2] += 0.5
    canvas, valid = _render_seam(frames, affines, 600, 330)
    # Interior rows that some frame covers must stay valid end to end.
    inner = valid[10:590, 20:300]
    assert (inner == 255).all(), np.argwhere(inner == 0)[:5]
    assert (canvas[10:590, 20:300].max(axis=2) > 0).all()
