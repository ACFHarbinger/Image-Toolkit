"""Pixel-art scalers: Scale2x/3x, EPX, xBR-style 2x, reduced hq2x, integer nearest."""

from __future__ import annotations

import numpy as np
import pytest
from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.classical.pixel import looks_like_pixel_art
from middleware.src.services.media.gif_upscale.registry import get_algorithm, list_algorithms

_RED = (1.0, 0.0, 0.0, 1.0)
_BLACK = (0.0, 0.0, 0.0, 1.0)
_WHITE = (1.0, 1.0, 1.0, 1.0)
_SOLID = (0.2, 0.4, 0.6, 0.8)


def _fill(height: int, width: int, color: tuple[float, float, float, float]) -> np.ndarray:
    frame = np.empty((height, width, 4), dtype=np.float32)
    frame[:] = color
    return frame


def _up(algorithm_id: str, frames: list[np.ndarray], scale: float, size: tuple[int, int] | None = None):
    opts: dict = {} if size is None else {"size": size}
    result = get_algorithm(algorithm_id).upscale(frames, scale, opts)
    assert len(result) == len(frames)
    return result


def _nearest(frame: np.ndarray, factor: int) -> np.ndarray:
    return np.repeat(np.repeat(frame, factor, axis=0), factor, axis=1)


@pytest.mark.parametrize(
    ("algorithm_id", "scales"),
    [
        ("scale2x", frozenset({2.0})),
        ("scale3x", frozenset({3.0})),
        ("epx", frozenset({2.0})),
        ("xbrz", frozenset({2.0})),
        ("hqx", frozenset({2.0})),
        ("integer-nearest", frozenset()),
    ],
)
def test_pixel_specs(algorithm_id: str, scales: frozenset[float]) -> None:
    spec = get_algorithm(algorithm_id).spec
    assert spec.kind == "classical"
    assert spec.content == "pixel"
    assert spec.family == "pixel"
    assert spec.license == "MIT"
    assert spec.needs_gpu is False
    assert spec.vram_mb_estimate == 0
    assert spec.weights_sha256 is None
    assert spec.supports_scale == scales
    assert spec.supports_downscale is False
    available, reason = spec.available()
    assert available is True
    assert reason == ""


def test_detector_is_not_registered() -> None:
    ids = {row["id"] for row in list_algorithms()}
    assert "looks_like_pixel_art" not in ids
    assert "looks-like-pixel-art" not in ids


def test_scale2x_corner_changes_one_product_and_solid_stays_solid() -> None:
    # Center E is black, with B and D red, so E0 copies D. Nearest would stay black.
    frame = _fill(3, 3, _BLACK)
    frame[0, 0] = _RED
    frame[0, 1] = _RED
    frame[1, 0] = _RED
    out = _up("scale2x", [frame], 2.0, (6, 6))[0]
    assert out.shape == (6, 6, 4)
    assert np.array_equal(out[2, 2], np.array(_RED, dtype=np.float32))
    assert np.array_equal(out[2, 3], np.array(_BLACK, dtype=np.float32))
    assert np.array_equal(out[3, 2], np.array(_BLACK, dtype=np.float32))
    assert np.array_equal(out[3, 3], np.array(_BLACK, dtype=np.float32))

    solid = _fill(4, 5, _SOLID)
    scaled = _up("scale2x", [solid, _fill(4, 5, _RED)], 2.0, (10, 8))
    assert np.all(scaled[0] == np.array(_SOLID, dtype=np.float32))
    assert np.all(scaled[1] == np.array(_RED, dtype=np.float32))


def test_scale2x_rejects_a_different_scale() -> None:
    frame = _fill(2, 2, _SOLID)
    with pytest.raises(AlgorithmError, match="scale2x"):
        _up("scale2x", [frame], 3.0, (6, 6))
    with pytest.raises(AlgorithmError, match="scale2x"):
        _up("scale2x", [frame], 3.0)


def test_scale3x_solid_stays_solid_and_a_horizontal_line_stays_a_bar() -> None:
    solid = _fill(3, 4, _SOLID)
    assert np.all(_up("scale3x", [solid], 3.0, (12, 9))[0] == np.array(_SOLID, dtype=np.float32))

    frame = _fill(5, 7, _BLACK)
    frame[2, 1:6] = _RED
    out = _up("scale3x", [frame], 3.0, (21, 15))[0]
    assert out.shape == (15, 21, 4)
    bar = out[6:9, 3:18]
    assert np.all(bar == np.array(_RED, dtype=np.float32))
    outside = out.copy()
    outside[6:9, 3:18] = _BLACK
    assert np.all(outside == np.array(_BLACK, dtype=np.float32))
    assert set(map(tuple, out.reshape(-1, 4).tolist())) <= {_RED, _BLACK}


def test_scale3x_rejects_scale_two() -> None:
    frame = _fill(2, 2, _RED)
    with pytest.raises(AlgorithmError, match="scale3x"):
        _up("scale3x", [frame], 2.0, (4, 4))


def test_epx_solid_stays_solid_and_differs_from_nearest() -> None:
    solid = _fill(3, 3, _SOLID)
    assert np.all(_up("epx", [solid], 2.0, (6, 6))[0] == np.array(_SOLID, dtype=np.float32))

    frame = _fill(3, 3, _BLACK)
    frame[0, 0] = _RED
    frame[0, 1] = _RED
    frame[1, 0] = _RED
    out = _up("epx", [frame], 2.0, (6, 6))[0]
    assert not np.array_equal(out, _nearest(frame, 2))
    assert np.array_equal(out[2, 2], np.array(_RED, dtype=np.float32))
    colors = {tuple(pixel) for pixel in out.reshape(-1, 4)}
    assert colors <= {_RED, _BLACK}


def test_xbrz_solid_stays_solid_and_a_diagonal_step_blends() -> None:
    solid = _fill(4, 4, _SOLID)
    assert np.all(_up("xbrz", [solid], 2.0, (8, 8))[0] == np.array(_SOLID, dtype=np.float32))

    # Bright 2x2 in the bottom-right. Pixel (1, 1) has dark diagonal neighbor (0, 0).
    frame = _fill(3, 3, _BLACK)
    frame[1:, 1:] = _WHITE
    out = _up("xbrz", [frame], 2.0, (6, 6))[0]
    corner = out[2:4, 2:4, :3]
    assert np.any((corner > 0.0) & (corner < 1.0))
    assert np.all((out[..., :3] >= 0.0) & (out[..., :3] <= 1.0))
    assert not np.array_equal(out, _nearest(frame, 2))


def test_hqx_solid_stays_solid_and_checker_stays_blocks() -> None:
    solid = _fill(3, 3, _SOLID)
    assert np.all(_up("hqx", [solid], 2.0, (6, 6))[0] == np.array(_SOLID, dtype=np.float32))

    frame = _fill(2, 2, _BLACK)
    frame[0, 1] = _WHITE
    frame[1, 0] = _WHITE
    out = _up("hqx", [frame], 2.0, (4, 4))[0]
    assert out.shape == (4, 4, 4)
    assert np.all(out[0:2, 0:2] == np.array(_BLACK, dtype=np.float32))
    assert np.all(out[0:2, 2:4] == np.array(_WHITE, dtype=np.float32))
    assert np.all(out[2:4, 0:2] == np.array(_WHITE, dtype=np.float32))
    assert np.all(out[2:4, 2:4] == np.array(_BLACK, dtype=np.float32))


def test_integer_nearest_repeats_blocks_and_alpha_and_rejects_a_partial_factor() -> None:
    frame = np.array(
        [
            [[1.0, 0.0, 0.0, 0.25], [0.0, 1.0, 0.0, 0.5]],
            [[0.0, 0.0, 1.0, 0.75], [1.0, 1.0, 0.0, 1.0]],
        ],
        dtype=np.float32,
    )
    out = _up("integer-nearest", [frame], 3.0, (6, 6))[0]
    assert out.shape == (6, 6, 4)
    assert np.array_equal(out[0:3, 0:3], np.broadcast_to(frame[0, 0], (3, 3, 4)))
    assert np.array_equal(out[0:3, 3:6], np.broadcast_to(frame[0, 1], (3, 3, 4)))
    assert np.array_equal(out[3:6, 0:3], np.broadcast_to(frame[1, 0], (3, 3, 4)))
    assert np.array_equal(out[3:6, 3:6], np.broadcast_to(frame[1, 1], (3, 3, 4)))

    with pytest.raises(AlgorithmError, match="integer-nearest"):
        _up("integer-nearest", [frame], 2.5, (5, 5))
    with pytest.raises(AlgorithmError, match="integer-nearest"):
        _up("integer-nearest", [frame], 0.5, (1, 1))


def test_empty_frame_list_stays_empty() -> None:
    assert _up("scale2x", [], 2.0, (4, 4)) == []


def test_looks_like_pixel_art_blocks_and_ramp() -> None:
    blocks = np.zeros((8, 8, 4), dtype=np.float32)
    blocks[0:4, 0:4] = (1.0, 0.0, 0.0, 1.0)
    blocks[0:4, 4:8] = (0.0, 1.0, 0.0, 1.0)
    blocks[4:8, 0:4] = (0.0, 0.0, 1.0, 1.0)
    blocks[4:8, 4:8] = (1.0, 1.0, 0.0, 0.5)
    assert looks_like_pixel_art(blocks) is True

    ramp = np.zeros((8, 8, 4), dtype=np.float32)
    for column in range(8):
        ramp[:, column, 0] = column / 7.0
        ramp[:, column, 3] = 1.0
    assert looks_like_pixel_art(ramp) is False
