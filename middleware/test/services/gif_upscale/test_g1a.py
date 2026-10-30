"""G1-A classical scalers: deringed Lanczos3, Catmull-Rom, sharper bicubic, EWA jinc."""

from __future__ import annotations

import numpy as np
import pytest
from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.registry import get_algorithm, list_algorithms
from middleware.src.services.media.subtabs import resample
from PIL import Image

_IDS = ("lanczos3-dering", "catmull-rom", "bicubic-sharper", "ewa-jinc")


def _run(algorithm_id: str, frames: list[np.ndarray], scale: float, size: tuple[int, int]) -> list[np.ndarray]:
    return get_algorithm(algorithm_id).upscale(frames, scale, {"size": size})


def _edge_slope(row: np.ndarray) -> float:
    """Trough-to-peak rise per pixel. C=0.75's ring makes this larger than Catmull-Rom."""
    dark = int(np.argmin(row))
    bright = int(np.argmax(row))
    run = abs(bright - dark)
    assert run > 0
    return float(row[bright] - row[dark]) / run


def test_registry_lists_the_four_classical_scalers() -> None:
    rows = {row["id"]: row for row in list_algorithms()}
    for algorithm_id in _IDS:
        row = rows[algorithm_id]
        assert row["family"] == "classical"
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


@pytest.mark.parametrize("algorithm_id", _IDS)
@pytest.mark.parametrize(("src", "dst"), [((5, 4), (9, 7)), ((8, 6), (3, 5))])
def test_constant_image_stays_constant(algorithm_id: str, src: tuple[int, int], dst: tuple[int, int]) -> None:
    height, width = src
    frame = np.full((height, width, 4), 0.2, dtype=np.float32)
    frame[..., 1] = 0.4
    frame[..., 2] = 0.7
    frame[..., 3] = 0.5
    untouched = frame.copy()
    out = _run(algorithm_id, [frame], dst[0] / width, dst)[0]
    assert out.shape == (dst[1], dst[0], 4)
    assert out.dtype == np.float32
    assert np.allclose(out[..., 0], 0.2, atol=1e-5)
    assert np.allclose(out[..., 1], 0.4, atol=1e-5)
    assert np.allclose(out[..., 2], 0.7, atol=1e-5)
    assert np.allclose(out[..., 3], 0.5, atol=1e-5)
    assert np.array_equal(frame, untouched)


@pytest.mark.parametrize("algorithm_id", _IDS)
def test_each_frame_stays_its_own_constant(algorithm_id: str) -> None:
    first = np.full((2, 3, 4), 0.25, dtype=np.float32)
    second = np.full((2, 3, 4), 0.75, dtype=np.float32)
    first[..., 3] = 1.0
    second[..., 3] = 0.5
    out = _run(algorithm_id, [first, second], 2.0, (5, 4))
    assert len(out) == 2
    assert np.allclose(out[0][..., 0], 0.25, atol=1e-5)
    assert np.allclose(out[0][..., 3], 1.0, atol=1e-5)
    assert np.allclose(out[1][..., 0], 0.75, atol=1e-5)
    assert np.allclose(out[1][..., 3], 0.5, atol=1e-5)


@pytest.mark.parametrize("algorithm_id", ("lanczos3-dering", "catmull-rom", "bicubic-sharper"))
def test_separable_scale_one_is_identity(algorithm_id: str) -> None:
    rng = np.random.default_rng(0)
    frame = rng.random((5, 6, 4), dtype=np.float64).astype(np.float32)
    frame[..., 3] = np.clip(frame[..., 3], 0.2, 1.0)
    out = _run(algorithm_id, [frame], 1.0, (6, 5))[0]
    assert np.allclose(out, frame, atol=1e-5)


def test_lanczos_vertical_step_stays_inside_the_unit_interval() -> None:
    frame = np.zeros((6, 8, 4), dtype=np.float32)
    frame[..., 3] = 1.0
    frame[:, 4:, :3] = 1.0
    out = _run("lanczos3-dering", [frame], 2.0, (16, 12))[0]
    assert out.shape == (12, 16, 4)
    assert float(out.min()) >= 0.0
    assert float(out.max()) <= 1.0
    edge = out[3, :, 0]
    assert float(edge.min()) < 0.05
    assert float(edge.max()) > 0.95
    assert np.any((edge > 0.05) & (edge < 0.95))


def test_catmull_rom_keeps_the_impulse_peak_at_the_center() -> None:
    frame = np.zeros((5, 5, 4), dtype=np.float32)
    frame[..., 3] = 1.0
    frame[2, 2, :3] = 1.0
    channel = _run("catmull-rom", [frame], 2.0, (10, 10))[0][..., 0]
    peak = float(channel.max())
    assert peak > 0.5
    assert np.allclose(channel[4:6, 4:6], peak, atol=1e-5)
    assert float(channel[0, 0]) < peak


def test_sharper_bicubic_step_is_steeper_than_catmull_rom() -> None:
    frame = np.zeros((4, 12, 4), dtype=np.float32)
    frame[..., 3] = 1.0
    frame[:, 6:, :3] = 1.0
    cat = _run("catmull-rom", [frame], 2.0, (24, 8))[0][2, :, 0]
    sharp = _run("bicubic-sharper", [frame], 2.0, (24, 8))[0][2, :, 0]
    assert float(sharp.max() - sharp.min()) > float(cat.max() - cat.min())
    assert _edge_slope(sharp) > _edge_slope(cat)


def test_ewa_checker_downscale_moves_toward_gray() -> None:
    frame = np.zeros((4, 4, 4), dtype=np.float32)
    frame[..., 3] = 1.0
    coords = np.arange(4)
    checker = ((coords[:, None] + coords[None, :]) % 2).astype(np.float32)
    frame[..., :3] = checker[..., None]
    channel = _run("ewa-jinc", [frame], 0.5, (2, 2))[0][..., 0]
    assert 0.2 < float(channel.mean()) < 0.8
    assert float(channel.min()) > 0.05
    assert float(channel.max()) < 0.95


@pytest.mark.parametrize("algorithm_id", _IDS)
def test_bad_input_raises_instead_of_falling_back(algorithm_id: str) -> None:
    frame = np.zeros((2, 2, 4), dtype=np.float32)
    frame[..., 3] = 1.0
    with pytest.raises(AlgorithmError, match="size"):
        get_algorithm(algorithm_id).upscale([frame], 2.0, {})
    with pytest.raises(AlgorithmError, match="size"):
        get_algorithm(algorithm_id).upscale([frame], 2.0, {"size": (0, 4)})
    with pytest.raises(AlgorithmError, match="scale"):
        get_algorithm(algorithm_id).upscale([frame], 0.0, {"size": (4, 4)})
    with pytest.raises(AlgorithmError, match="HxWx4"):
        get_algorithm(algorithm_id).upscale([np.zeros((2, 2, 3), dtype=np.float32)], 2.0, {"size": (4, 4)})
    broken = frame.copy()
    broken[0, 0, 0] = np.nan
    with pytest.raises(AlgorithmError, match="non-finite"):
        get_algorithm(algorithm_id).upscale([broken], 2.0, {"size": (4, 4)})
    assert _run(algorithm_id, [], 2.0, (4, 4)) == []


def test_pipeline_writes_each_algorithm_into_tmp_path(tmp_path) -> None:
    source = tmp_path / "step.gif"
    image = Image.new("RGBA", (4, 4), (0, 0, 0, 255))
    for x in range(2, 4):
        for y in range(4):
            image.putpixel((x, y), (255, 255, 255, 255))
    image.save(source, format="GIF", duration=30, loop=1)
    image.close()
    for algorithm_id in _IDS:
        output = tmp_path / f"{algorithm_id}.gif"
        result = resample(
            {
                "input_path": str(source),
                "output_path": str(output),
                "mode": "factor",
                "factor": 2,
                "algorithm": algorithm_id,
            }
        )
        assert result["success"] is True, result["message"]
        assert (result["width"], result["height"]) == (8, 8)
        assert output.is_file()
        with Image.open(output) as gif:
            assert gif.size == (8, 8)
            assert gif.n_frames == 1
