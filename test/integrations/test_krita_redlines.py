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


def test_maps_selected_head_redlines_into_only_its_sheet_cell():
    module = _module()
    review = {
        "id": "r",
        "redlines": [{"geometry": [[0.0, 0.2], [1.0, 0.8]], "explanation": "guide"}],
    }
    mapped = module.map_review_redlines_to_sheet(review, 3)
    assert mapped["redlines"][0]["geometry"] == [[0.6, 0.2], [0.8, 0.8]]
    assert review["redlines"][0]["geometry"] == [[0.0, 0.2], [1.0, 0.8]]
    with pytest.raises(ValueError, match="cell"):
        module.map_review_redlines_to_sheet(review, 5)


def test_maps_feature_redlines_into_row_major_matrix_cell():
    module = _module()
    review = {"redlines": [{"geometry": [[0.0, 0.0], [1.0, 1.0]]}]}
    mapped = module.map_review_redlines_to_matrix(review, 4)
    assert mapped["redlines"][0]["geometry"] == [
        [1 / 3, 1 / 2],
        [2 / 3, 1.0],
    ]


class LayerStub:
    def __init__(self, name, remove_result=True):
        self._name = name
        self.locked = False
        self.remove_result = remove_result
        self.removed = False

    def name(self):
        return self._name

    def setName(self, name):  # noqa: N802
        self._name = name

    def setLocked(self, locked):  # noqa: N802
        self.locked = locked

    def remove(self):
        self.removed = self.remove_result
        return self.remove_result


def test_accept_preview_is_owned_and_idempotent():
    module = _module()
    layer = LayerStub(module.PREVIEW_LAYER_PREFIX + "review")
    assert module.accept_preview(layer)
    assert layer.name() == module.ACCEPTED_LAYER_PREFIX + "review"
    assert layer.locked
    assert not module.accept_preview(layer)


def test_reject_preview_removes_only_owned_pending_layer():
    module = _module()
    layer = LayerStub(module.PREVIEW_LAYER_PREFIX + "review")
    assert module.reject_preview(layer)
    assert layer.removed
    with pytest.raises(ValueError, match="not owned"):
        module.reject_preview(LayerStub("Artwork"))
