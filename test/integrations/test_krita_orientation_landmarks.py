"""Tests for active-layer selection and specialized orientation prompts."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _module():
    path = (
        Path(__file__).parents[2]
        / "integrations/krita/pykrita/cel_shaded_generator/orientation_landmarks.py"
    )
    spec = importlib.util.spec_from_file_location("krita_orientation_landmarks", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_active_named_layer_selects_view_and_sheet_cell():
    module = _module()
    assert module.selected_orientation_view(
        SimpleNamespace(name="04 Right Three-Quarter Construction")
    ) == ("right_three_quarter", 3)

    class Node:
        def name(self):
            return "01 Left Profile Construction"

    assert module.selected_orientation_view(Node()) == ("left_profile", 0)
    with pytest.raises(ValueError, match="not one of"):
        module.selected_orientation_view(SimpleNamespace(name="Artwork"))


def test_active_design_layer_selects_view_cell_and_variant():
    module = _module()
    assert module.selected_design_view(
        SimpleNamespace(name="03 Long Tapered Front Construction")
    ) == ("front", 2, "long_tapered")
    assert module.selected_design_view(
        SimpleNamespace(name="05 Selected Variant Right Three-Quarter Construction")
    ) == ("right_three_quarter", 4, "selected_variant")
    with pytest.raises(ValueError, match="not one of"):
        module.selected_design_view(SimpleNamespace(name="Artwork"))


@pytest.mark.parametrize(
    "view, kind, expected_key",
    [
        ("left_profile", "profile", "front_cranium_edge"),
        ("right_profile", "profile", "front_cranium_edge"),
        ("left_three_quarter", "three_quarter", "left_contour"),
        ("right_three_quarter", "three_quarter", "left_contour"),
    ],
)
def test_view_specific_collectors_return_specialized_landmarks(view, kind, expected_key):
    module = _module()
    collector = module.OrientationLandmarkCollector(view)
    for index in range(len(collector.prompts)):
        collector.add(0.2 + index * 0.02, 0.3 + index * 0.02)
    result = collector.result()
    assert collector.kind == kind
    assert expected_key in result
    assert result["cranium_radius"] > 0


def test_front_uses_existing_calibrated_collector():
    with pytest.raises(ValueError, match="front orientation"):
        _module().OrientationLandmarkCollector("front")
