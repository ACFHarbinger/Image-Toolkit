"""Anime4K v1 push: registry row, constant frames, and a thin bright line."""

from __future__ import annotations

import numpy as np
import pytest
from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.registry import get_algorithm, list_algorithms


def test_anime4k_registration() -> None:
    row = next(item for item in list_algorithms() if item["id"] == "anime4k")
    assert row["family"] == "anime4k"
    assert row["content"] == "anime"
    assert row["kind"] == "classical"
    assert row["supports_scale"] == []
    assert row["supports_downscale"] is True
    assert row["needs_gpu"] is False
    assert row["vram_mb_estimate"] == 0
    assert row["license"] == "MIT"
    assert row["weights_sha256"] is None
    assert row["available"] is True
    assert row["reason"] == ""


def test_constant_image_stays_constant() -> None:
    color = np.array([0.2, 0.4, 0.6, 0.5], dtype=np.float32)
    frame = np.broadcast_to(color, (5, 7, 4)).copy()
    original = frame.copy()
    out = get_algorithm("anime4k").upscale([frame], 2.0, {"size": (13, 9)})[0]
    assert out.shape == (9, 13, 4)
    assert out.dtype == np.float32
    assert np.allclose(out, color, rtol=0, atol=1e-4)
    assert np.array_equal(frame, original)


def test_bright_line_center_beats_bilinear() -> None:
    height, width = 12, 8
    line_row = 6
    frame = np.zeros((height, width, 4), dtype=np.float32)
    frame[..., 3] = 1
    frame[line_row, :, :3] = 1
    target = (width * 2, height * 2)
    scaled = get_algorithm("anime4k").upscale([frame], 2.0, {"size": target})[0]
    bilinear = _bilinear(frame, target)
    rows = _line_center_rows(line_row, height, height * 2)
    assert _mean_luma(scaled, rows) > _mean_luma(bilinear, rows)


def test_dark_line_edge_moves_toward_the_background() -> None:
    frame = np.ones((9, 7, 4), dtype=np.float32)
    frame[3:6, :, :3] = 0
    out = get_algorithm("anime4k").upscale([frame], 1.0, {"size": (7, 9)})[0]
    luma = _luma(out)
    assert luma[3].mean() > luma[4].mean()
    assert luma[5].mean() > luma[4].mean()
    assert luma[4].mean() < 0.05


@pytest.mark.parametrize("size", [(0, 8), (8, 0), (-1, 4)])
def test_non_positive_target_size_is_an_algorithm_error(size: tuple[int, int]) -> None:
    frame = np.zeros((4, 4, 4), dtype=np.float32)
    frame[..., 3] = 1
    with pytest.raises(AlgorithmError):
        get_algorithm("anime4k").upscale([frame], 2.0, {"size": size})


def _line_center_rows(src_row: int, src_h: int, dst_h: int) -> tuple[int, int]:
    """The two output rows that straddle a source row under the pixel-center map."""
    center = (src_row + 0.5) * dst_h / src_h - 0.5
    start = int(np.floor(center))
    return start, start + 1


def _mean_luma(frame: np.ndarray, rows: tuple[int, int]) -> float:
    return float(_luma(frame)[rows[0] : rows[1] + 1].mean())


def _luma(frame: np.ndarray) -> np.ndarray:
    return frame[..., 0] * 0.299 + frame[..., 1] * 0.587 + frame[..., 2] * 0.114


def _bilinear(frame: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Plain pixel-center bilinear. The line regression compares against this, not Lanczos."""
    src_h, src_w = frame.shape[:2]
    dst_w, dst_h = size
    ys = (np.arange(dst_h, dtype=np.float32) + 0.5) * (src_h / dst_h) - 0.5
    xs = (np.arange(dst_w, dtype=np.float32) + 0.5) * (src_w / dst_w) - 0.5
    x0 = np.floor(xs).astype(np.int32)
    y0 = np.floor(ys).astype(np.int32)
    fx = (xs - x0).astype(np.float32)[None, :, None]
    fy = (ys - y0).astype(np.float32)[:, None, None]
    x0c = np.clip(x0, 0, src_w - 1)[None, :]
    x1c = np.clip(x0 + 1, 0, src_w - 1)[None, :]
    y0c = np.clip(y0, 0, src_h - 1)[:, None]
    y1c = np.clip(y0 + 1, 0, src_h - 1)[:, None]
    return (
        frame[y0c, x0c] * (1 - fy) * (1 - fx)
        + frame[y0c, x1c] * (1 - fy) * fx
        + frame[y1c, x0c] * fy * (1 - fx)
        + frame[y1c, x1c] * fy * fx
    ).astype(np.float32, copy=False)
