"""Tests for controlled-asymmetry layer and landmark contracts."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _module():
    path = (
        Path(__file__).parents[3]
        / "integrations/krita/pykrita/cel_shaded_generator/asymmetry_landmarks.py"
    )
    spec = importlib.util.spec_from_file_location("krita_asymmetry_landmarks", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_layer_selects_stage_cell_and_intent_requirement():
    module = _module()
    assert module.selected_asymmetry_stage(
        SimpleNamespace(name="03 Persistent Design Asymmetry")
    ) == ("design", 2, True)
    assert module.selected_asymmetry_stage(
        SimpleNamespace(name="02 Corrected Accidental Drift")
    ) == ("corrected_drift", 1, False)
    with pytest.raises(ValueError, match="not one of"):
        module.selected_asymmetry_stage(SimpleNamespace(name="Artwork"))


def test_asymmetry_collector_returns_full_comparison_set():
    collector = _module().AsymmetryLandmarkCollector()
    for index in range(len(collector.prompts)):
        collector.add(0.1 + index * 0.02, 0.2 + index * 0.02)
    assert len(collector.result()) == 14
