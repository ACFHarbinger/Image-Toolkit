"""Tests for ordered normalized landmark collection."""

import importlib.util
from pathlib import Path

import pytest


def _collector_type():
    path = (
        Path(__file__).parents[2] / "integrations/krita/pykrita/cel_shaded_generator/landmarks.py"
    )
    spec = importlib.util.spec_from_file_location("krita_landmarks", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LandmarkCollector


def _points():
    return [
        (0.5, 0.4),
        (0.75, 0.4),
        (0.5, 0.15),
        (0.5, 0.85),
        (0.3, 0.4),
        (0.7, 0.4),
        (0.34, 0.65),
        (0.66, 0.65),
        (0.5, 0.85),
    ]


def test_collects_ordered_points_and_derives_cranial_radius():
    collector = _collector_type()()
    for point in _points():
        collector.add(*point)
    result = collector.result()
    assert collector.complete
    assert result["cranium_center"] == (0.5, 0.4)
    assert result["cranium_radius"] == pytest.approx(0.25)
    assert result["chin"] == (0.5, 0.85)


def test_undo_and_reset_keep_prompt_state_consistent():
    collector = _collector_type()()
    collector.add(0.5, 0.4)
    collector.undo()
    assert "center" in collector.prompt
    collector.add(0.5, 0.4)
    collector.reset()
    assert collector.points == ()


def test_rejects_out_of_bounds_or_incomplete_landmarks():
    collector = _collector_type()()
    with pytest.raises(ValueError, match="normalized"):
        collector.add(1.1, 0.5)
    with pytest.raises(ValueError, match="all landmarks"):
        collector.result()


def test_rejects_zero_cranial_radius():
    collector = _collector_type()()
    points = _points()
    points[1] = points[0]
    for point in points:
        collector.add(*point)
    with pytest.raises(ValueError, match="distinct"):
        collector.result()
