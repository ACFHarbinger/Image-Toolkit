"""Area, linear-light, and SSIM GIF downscalers."""

from __future__ import annotations

import numpy as np
import pytest
from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.registry import get_algorithm, list_algorithms
from PIL import Image

IDS = ("area", "linear-light", "ssim-downscale")


def run(algorithm_id: str, frames: list[np.ndarray], size: tuple[int, int], scale: float = 0.5):
    return get_algorithm(algorithm_id).upscale(frames, scale, {"size": size})


def test_downscalers_register_with_downscale_metadata() -> None:
    rows = {row["id"]: row for row in list_algorithms()}
    for algorithm_id in IDS:
        row = rows[algorithm_id]
        assert row["family"] == "downscale"
        assert row["content"] == "any"
        assert row["kind"] == "classical"
        assert row["supports_scale"] == []
        assert row["supports_downscale"] is True
        assert row["needs_gpu"] is False
        assert row["vram_mb_estimate"] == 0
        assert row["license"] == "MIT"
        assert row["weights_sha256"] is None
        assert row["available"] is True
        assert row["reason"] == ""


def test_area_averages_black_and_white_to_gray() -> None:
    frame = np.zeros((2, 2, 4), np.float32)
    frame[..., 3] = 1
    frame[0, 1, :3] = 1
    frame[1, 0, :3] = 1
    out = run("area", [frame], (1, 1))[0]
    assert out.shape == (1, 1, 4)
    assert out.dtype == np.float32
    assert np.allclose(out[0, 0, :3], 0.5, atol=1e-3)
    assert np.allclose(out[0, 0, 3], 1)


def test_area_fractional_coverage_is_a_box_mean() -> None:
    frame = np.zeros((1, 3, 4), np.float32)
    frame[..., 3] = 1
    frame[0, 2, :3] = 1
    out = run("area", [frame], (2, 1))[0]
    assert out.shape == (1, 2, 4)
    assert np.allclose(out[0, :, 0], [0.0, 2.0 / 3.0], atol=1e-5)


@pytest.mark.parametrize("algorithm_id", IDS)
@pytest.mark.parametrize("color", (0.0, 0.04045, 0.3, 1.0))
@pytest.mark.parametrize("alpha", (0.4, 1.0))
def test_constant_stays_constant(algorithm_id: str, color: float, alpha: float) -> None:
    frame = np.full((5, 7, 4), np.float32(color), np.float32)
    frame[..., 3] = np.float32(alpha)
    before = frame.copy()
    out = run(algorithm_id, [frame], (3, 2), scale=3.0)[0]
    assert np.array_equal(frame, before)
    assert out.shape == (2, 3, 4)
    expected = np.array([color, color, color, alpha], np.float32)
    assert np.allclose(out, expected, atol=1e-5, rtol=0)


def test_transparent_pixel_stays_clear_and_does_not_tint() -> None:
    mixed = np.zeros((1, 2, 4), np.float32)
    mixed[0, 0] = (1, 0, 0, 1)
    mixed[0, 1] = (0, 1, 0, 0)
    clear = np.zeros((2, 2, 4), np.float32)
    clear[..., 0] = 0.2
    clear[..., 1] = 0.8
    clear[..., 2] = 0.4
    for algorithm_id in IDS:
        mixed_out = run(algorithm_id, [mixed], (1, 1))[0]
        assert np.allclose(mixed_out[0, 0], (1, 0, 0, 0.5), atol=1e-5)
        clear_out = run(algorithm_id, [clear], (1, 1))[0]
        assert clear_out[0, 0, 3] == 0
        assert np.allclose(clear_out[0, 0, :3], 0)


def test_linear_light_ramp_differs_from_gamma_area() -> None:
    frame = np.zeros((1, 2, 4), np.float32)
    frame[..., 3] = 1
    frame[0, 1, :3] = 1
    area = run("area", [frame], (1, 1))[0]
    linear = run("linear-light", [frame], (1, 1))[0]
    assert np.allclose(area[0, 0, :3], 0.5, atol=1e-5)
    assert abs(float(linear[0, 0, 0]) - float(area[0, 0, 0])) > 1e-3
    assert np.allclose(linear[0, 0, 3], 1)


def test_ssim_stripes_deviate_from_gray_more_than_area() -> None:
    frame = np.zeros((8, 4, 4), np.float32)
    frame[..., 3] = 1
    frame[1::2, :, :3] = 1
    area = run("area", [frame], (4, 4))[0]
    ssim = run("ssim-downscale", [frame], (4, 4))[0]
    area_mad = float(np.mean(np.abs(area[..., :3] - 0.5)))
    ssim_mad = float(np.mean(np.abs(ssim[..., :3] - 0.5)))
    assert ssim.shape == (4, 4, 4)
    assert ssim_mad > area_mad
    assert np.allclose(ssim[..., 3], 1)


def test_ssim_clamps_every_channel() -> None:
    frame = np.zeros((8, 8, 4), np.float32)
    frame[..., 3] = 1
    frame[3:5, 3:5, :3] = 1
    out = run("ssim-downscale", [frame], (4, 4))[0]
    assert np.all(out >= 0.0)
    assert np.all(out <= 1.0)


@pytest.mark.parametrize("algorithm_id", IDS)
@pytest.mark.parametrize("size", [(8, 4), (4, 8), (8, 8)])
def test_growth_raises_and_does_not_call_pillow(monkeypatch, algorithm_id: str, size: tuple[int, int]) -> None:
    def fail_resize(*args, **kwargs):
        raise AssertionError("downscaler called Pillow")

    monkeypatch.setattr(Image.Image, "resize", fail_resize)
    frame = np.zeros((4, 4, 4), np.float32)
    frame[..., 3] = 1
    with pytest.raises(AlgorithmError, match=f"{algorithm_id} does not upscale"):
        run(algorithm_id, [frame], size)


def test_downscale_does_not_call_pillow(monkeypatch) -> None:
    def fail_resize(*args, **kwargs):
        raise AssertionError("downscaler called Pillow")

    monkeypatch.setattr(Image.Image, "resize", fail_resize)
    frame = np.full((4, 6, 4), 0.25, np.float32)
    frame[..., 3] = 1
    out = run("area", [frame, frame], (3, 2))
    assert len(out) == 2
    assert out[0].shape == (2, 3, 4)
    assert np.allclose(out[1][..., 0], 0.25, atol=1e-5)
