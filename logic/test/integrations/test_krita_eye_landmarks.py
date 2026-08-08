"""Tests for eye exercise active-layer selection and prompts."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _module():
    path = (
        Path(__file__).parents[3]
        / "integrations/krita/pykrita/cel_shaded_generator/eye_landmarks.py"
    )
    spec = importlib.util.spec_from_file_location("krita_eye_landmarks", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_named_layer_selects_eye_view_stage_and_cell():
    module = _module()
    assert module.selected_eye_view(
        SimpleNamespace(name="04 Stylized Right Three-Quarter Expression")
    ) == ("right_three_quarter", "style_expression", 3)
    with pytest.raises(ValueError, match="not one of"):
        module.selected_eye_view(SimpleNamespace(name="Artwork"))


def test_eye_collector_returns_all_named_normalized_points():
    collector = _module().EyeLandmarkCollector()
    for index in range(len(collector.prompts)):
        collector.add(0.1 + index * 0.02, 0.2 + index * 0.02)
    assert collector.complete
    result = collector.result()
    assert len(result) == 16
    assert "left_upper_peak" in result
    assert "right_iris_bottom" in result
