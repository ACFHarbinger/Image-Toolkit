"""Tests for character-variation layer selection."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _module():
    package = Path(__file__).parents[2] / "integrations/krita/pykrita/cel_shaded_generator"
    package_module = ModuleType("cel_shaded_generator")
    package_module.__path__ = [str(package)]
    sys.modules["cel_shaded_generator"] = package_module
    path = package / "variation_landmarks.py"
    spec = importlib.util.spec_from_file_location("cel_shaded_generator.variation_landmarks", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_variation_layer_selects_stage_and_cell():
    module = _module()
    assert module.selected_variation_stage(
        SimpleNamespace(name="06 Selected Right Three-Quarter Identity Check")
    ) == ("selected_turned", 5)
    with pytest.raises(ValueError, match="not one of"):
        module.selected_variation_stage(SimpleNamespace(name="Artwork"))
