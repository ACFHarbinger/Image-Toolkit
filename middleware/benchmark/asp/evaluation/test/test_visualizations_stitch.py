"""Synthetic checks for stitch-seam pixel views. No files, no GUI."""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import cv2  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

from ..logic.visualizations_stitch import (  # noqa: E402
    band_intersection_figure,
    coverage_gap,
    delta_e_map,
    edge_disagreement,
    ghost_residual,
    laplacian_residual,
    local_ssim_map,
    seam_energy_figure,
)


def test_identical_maps_are_near_black() -> None:
    image = np.random.default_rng(0).integers(0, 256, size=(40, 30, 3), dtype=np.uint8)
    for build in (local_ssim_map, delta_e_map, laplacian_residual):
        heat = build(image, image.copy())
        assert heat.dtype == np.uint8
        assert heat.shape == (40, 30, 3)
        assert float(heat.mean()) < 5.0


def test_ghost_residual_lines_up_a_column_roll() -> None:
    """64x64, not 40x30.

    A column ramp, a row ramp, and one saturated dot. phaseCorrelate's peak
    is stable on this canvas; a 6-column roll of a 40x30 patch is the flaky size.
    """
    height = width = 64
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :, 1] = np.linspace(0, 255, width, dtype=np.uint8)[None, :]
    image[:, :, 0] = np.linspace(0, 180, height, dtype=np.uint8)[:, None]
    image[22, 18] = (255, 255, 255)
    rolled = np.roll(image, 6, axis=1)
    heat = ghost_residual(image, rolled)
    gray_a = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray_b = cv2.cvtColor(rolled, cv2.COLOR_BGR2GRAY).astype(np.float32)
    unaligned = float(np.abs(gray_a - gray_b).mean())
    assert heat.shape == (height, width, 3)
    assert float(heat.mean()) < unaligned


def test_coverage_gap_marks_only_the_uncovered_half() -> None:
    height, width = 40, 40
    partial = np.zeros((height, width, 3), dtype=np.uint8)
    partial[:, width // 2 :] = 200
    full = np.full((height, width, 3), 200, dtype=np.uint8)
    gap = coverage_gap(partial, full)
    assert np.any(gap != 0)
    assert np.all(gap[:, width // 2 :] == 0)


def test_seam_energy_figure_title() -> None:
    image = np.zeros((48, 32, 3), dtype=np.uint8)
    image[20, :, :] = 255
    fig = seam_energy_figure(image)
    try:
        assert "Seam energy" in fig.axes[0].get_title()
    finally:
        plt.close(fig)


def test_band_intersection_rejects_fewer_than_two_bands() -> None:
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        band_intersection_figure(image, bands=1)


def test_edge_disagreement_matches_downsampled_shape() -> None:
    rng = np.random.default_rng(1)
    first = rng.integers(0, 256, size=(40, 30, 3), dtype=np.uint8)
    second = rng.integers(0, 256, size=(40, 30, 3), dtype=np.uint8)
    heat = edge_disagreement(first, second)
    assert heat.dtype == np.uint8
    assert heat.ndim == 3
    assert heat.shape[2] == 3
    assert heat.shape[0] <= 40
    assert heat.shape[:2] == first.shape[:2]
