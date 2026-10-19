"""Tests for specialized feature-layer landmark workflows."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _module():
    path = (
        Path(__file__).parents[3]
        / "integrations/krita/pykrita/cel_shaded_generator/feature_landmarks.py"
    )
    spec = importlib.util.spec_from_file_location("krita_feature_landmarks", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_named_layer_selects_feature_view_and_matrix_cell():
    module = _module()
    assert module.selected_feature_view(
        SimpleNamespace(name="06 Right Three-Quarter Ear Construction")
    ) == ("ear", "right_three_quarter", 5)
    with pytest.raises(ValueError, match="not one of"):
        module.selected_feature_view(SimpleNamespace(name="Artwork"))


@pytest.mark.parametrize(
    "feature,view,count",
    [
        ("nose", "front", 10),
        ("mouth", "right_three_quarter", 10),
        ("ear", "front", 14),
        ("ear", "right_three_quarter", 10),
    ],
)
def test_each_feature_uses_its_specialized_prompt_contract(feature, view, count):
    collector = _module().FeatureLandmarkCollector(feature, view)
    for index in range(count):
        collector.add(0.1 + index * 0.02, 0.2 + index * 0.02)
    assert len(collector.result()) == count
