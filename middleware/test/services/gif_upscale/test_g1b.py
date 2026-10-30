"""G1-B classical scalers: FSR1 EASU+RCAS, NEDI, and guided-filter detail."""

from __future__ import annotations

import numpy as np
import pytest
from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.registry import get_algorithm, list_algorithms

_IDS = ("fsr1-easu", "nedi", "guided-detail")


def _luma(frame: np.ndarray) -> np.ndarray:
    return 0.2126 * frame[..., 0] + 0.7152 * frame[..., 1] + 0.0722 * frame[..., 2]


def _constant(height: int, width: int, value: float) -> np.ndarray:
    frame = np.full((height, width, 4), value, dtype=np.float32)
    frame[..., 3] = 1.0
    return frame


def _run(algorithm_id: str, frames: list[np.ndarray], scale: float, size: tuple[int, int]) -> list[np.ndarray]:
    return get_algorithm(algorithm_id).upscale(frames, scale, {"size": size})


def test_g1b_algorithms_register_with_the_classical_contract() -> None:
    rows = {row["id"]: row for row in list_algorithms()}
    for algorithm_id in _IDS:
        row = rows[algorithm_id]
        assert row["family"] == "classical"
        assert row["content"] == "any"
        assert row["kind"] == "classical"
        assert row["needs_gpu"] is False
        assert row["vram_mb_estimate"] == 0
        assert row["license"] == "MIT"
        assert row["weights_sha256"] is None
        assert row["available"] is True
        assert row["reason"] == ""
    assert rows["fsr1-easu"]["supports_scale"] == [2.0]
    assert rows["fsr1-easu"]["supports_downscale"] is False
    assert rows["nedi"]["supports_scale"] == [2.0]
    assert rows["nedi"]["supports_downscale"] is False
    assert rows["guided-detail"]["supports_scale"] == []
    assert rows["guided-detail"]["supports_downscale"] is True


def test_fsr1_constant_stays_constant_and_step_beats_bilinear() -> None:
    frames = [_constant(4, 6, 0.3), _constant(4, 6, 0.3)]
    frames[1][..., :3] = 0.8
    out = _run("fsr1-easu", frames, 2.0, (12, 8))
    assert len(out) == 2
    assert out[0].shape == (8, 12, 4)
    assert out[0].dtype == np.float32
    assert np.allclose(out[0], frames[0][0, 0], atol=1e-5)
    assert np.allclose(out[1][..., :3], 0.8, atol=1e-5)
    assert np.allclose(out[1][..., 3], 1.0, atol=1e-5)

    source = _constant(8, 8, 0.0)
    source[:, 4:, :3] = 1.0
    scaled = _run("fsr1-easu", [source], 2.0, (16, 16))[0]
    bilinear = _run("bilinear", [source], 2.0, (16, 16))[0]
    assert scaled.shape == (16, 16, 4)
    fsr_row = _luma(scaled)[scaled.shape[0] // 2]
    bilinear_row = _luma(bilinear)[bilinear.shape[0] // 2]
    fsr_mid = int(np.sum((fsr_row > 0.1) & (fsr_row < 0.9)))
    bilinear_mid = int(np.sum((bilinear_row > 0.1) & (bilinear_row < 0.9)))
    assert bilinear_mid > 0
    assert fsr_mid < bilinear_mid


def test_fsr1_refuses_a_scale_other_than_two() -> None:
    frame = _constant(8, 8, 0.2)
    with pytest.raises(AlgorithmError, match="does not downscale"):
        _run("fsr1-easu", [frame], 0.5, (4, 4))
    with pytest.raises(AlgorithmError, match="supports scales"):
        _run("fsr1-easu", [frame], 3.0, (24, 24))
    with pytest.raises(AlgorithmError, match="supports scales"):
        _run("fsr1-easu", [frame], 2.0, (16, 18))


def test_nedi_constant_and_horizontal_edge() -> None:
    frame = _constant(5, 7, 1.0 / 3.0)
    out = _run("nedi", [frame, frame], 2.0, (14, 10))
    assert len(out) == 2
    assert out[0].shape == (10, 14, 4)
    assert out[0].dtype == np.float32
    assert np.allclose(out[0], frame[0, 0], atol=1e-5)
    assert np.allclose(out[1], frame[0, 0], atol=1e-5)

    height, width = 8, 8
    src = np.zeros((height, width, 4), dtype=np.float32)
    ramp = np.linspace(0.05, 0.25, width, dtype=np.float32)
    src[..., :3] = ramp[None, :, None]
    mid = height // 2
    src[mid:, :, :3] += 0.6
    src[..., 3] = 1.0
    scaled = _run("nedi", [src], 2.0, (width * 2, height * 2))[0]
    level = _luma(scaled)
    out_h = height * 2
    sy = (np.arange(out_h) + 0.5) * (height / out_h) - 0.5
    above_rows = np.flatnonzero((sy >= mid - 1) & (sy < mid - 0.5))
    below_rows = np.flatnonzero((sy >= mid - 0.5) & (sy < mid))
    assert above_rows.size == 1
    assert below_rows.size == 1
    ox = np.arange(width * 2)
    sx = (ox + 0.5) * (width / (width * 2)) - 0.5
    x0 = np.floor(sx).astype(int)
    valid = (x0 >= 1) & (x0 + 1 < width)
    x0v = x0[valid]
    above = level[above_rows[0], valid]
    below = level[below_rows[0], valid]
    vertical_above = src[mid - 1, x0v, 0]
    vertical_below = src[mid, x0v, 0]
    # Diagonal pair crosses the edge and shifts a column, which a horizontal edge must not copy.
    smear_above = 0.5 * (src[mid - 1, x0v - 1, 0] + src[mid, x0v + 1, 0])
    smear_below = 0.5 * (src[mid, x0v - 1, 0] + src[mid - 1, x0v + 1, 0])
    assert np.mean(np.abs(above - vertical_above)) < np.mean(np.abs(smear_above - vertical_above))
    assert np.mean(np.abs(below - vertical_below)) < np.mean(np.abs(smear_below - vertical_below))


def test_nedi_refuses_a_scale_other_than_two() -> None:
    frame = _constant(8, 8, 0.2)
    with pytest.raises(AlgorithmError, match="does not downscale"):
        _run("nedi", [frame], 0.5, (4, 4))
    with pytest.raises(AlgorithmError, match="supports scales"):
        _run("nedi", [frame], 4.0, (32, 32))


def test_guided_detail_keeps_flats_and_edge_contrast() -> None:
    constant = _constant(8, 8, 0.25)
    for size, scale in (((4, 4), 0.5), ((8, 8), 1.0), ((12, 10), 1.5), ((16, 16), 2.0)):
        out = _run("guided-detail", [constant], scale, size)
        assert len(out) == 1
        assert out[0].shape == (size[1], size[0], 4)
        assert out[0].dtype == np.float32
        assert np.allclose(out[0][..., :3], 0.25, atol=1e-5)
        assert np.allclose(out[0][..., 3], 1.0, atol=1e-5)

    src = _constant(12, 12, 0.4)
    src[:, 6, :3] = 1.0
    out = _run("guided-detail", [src], 2.0, (24, 24))[0]
    bilinear = _run("bilinear", [src], 2.0, (24, 24))[0]
    assert np.allclose(out[:, :8, :3], 0.4, atol=1e-5)
    assert np.allclose(out[:, -8:, :3], 0.4, atol=1e-5)
    out_row = _luma(out)[out.shape[0] // 2]
    bilinear_row = _luma(bilinear)[bilinear.shape[0] // 2]
    out_contrast = float(out_row.max() - out_row.min())
    bilinear_contrast = float(bilinear_row.max() - bilinear_row.min())
    assert out_contrast + 1e-5 >= bilinear_contrast


def test_guided_detail_refuses_a_non_positive_target() -> None:
    frame = _constant(4, 4, 0.2)
    with pytest.raises(AlgorithmError, match="target size must be positive"):
        _run("guided-detail", [frame], 1.0, (0, 4))
    assert _run("guided-detail", [], 2.0, (8, 8)) == []
