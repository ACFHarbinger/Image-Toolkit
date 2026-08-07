"""Tests for deterministic Krita 5.x-compatible redline rasterization."""

import importlib.util
from pathlib import Path

import pytest


def _module():
    path = Path(__file__).parents[2] / "integrations/krita/pykrita/cel_shaded_generator/redlines.py"
    spec = importlib.util.spec_from_file_location("krita_redlines", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rasterizes_normalized_line_as_transparent_bgra():
    module = _module()
    pixels = module.rasterize_redlines(10, 10, [{"geometry": [[0.0, 0.0], [1.0, 1.0]]}])
    assert len(pixels) == 10 * 10 * 4
    assert pixels[:4] == bytes(module.REDLINE_BGRA)
    assert pixels[-4:] == bytes(module.REDLINE_BGRA)
    assert pixels[(0 * 10 + 9) * 4 : (0 * 10 + 9) * 4 + 4] == b"\0\0\0\0"


@pytest.mark.parametrize(
    "redlines",
    [
        [{"geometry": [[0.5, 0.5]]}],
        [{"geometry": [[-0.1, 0.5], [0.5, 0.5]]}],
        [{"geometry": "not points"}],
    ],
)
def test_rejects_invalid_engine_geometry(redlines):
    with pytest.raises(ValueError):
        _module().rasterize_redlines(10, 10, redlines)


def test_rejects_unbounded_canvas_allocation():
    with pytest.raises(ValueError, match="too large"):
        _module().rasterize_redlines(20_000, 20_000, [])
