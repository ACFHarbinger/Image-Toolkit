"""Headless tests for the existing-docker progress presentation."""

import importlib.util
from pathlib import Path


def _module():
    path = (
        Path(__file__).parents[2]
        / "integrations/krita/pykrita/cel_shaded_generator/progress_view.py"
    )
    spec = importlib.util.spec_from_file_location("krita_progress_view", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot():
    identity = {
        "exercise_version": "1",
        "method_id": "method",
        "rubric_id": "rubric",
        "rubric_version": "1",
    }
    return {
        "retain_learning_progress": True,
        "exercises": [
            {
                "exercise_id": "head",
                "attempts": [
                    {
                        "attempt_id": "a",
                        "reviews": [
                            identity
                            | {
                                "review_id": "r1",
                                "measurements": {
                                    "head_axis_consistency": 0.4,
                                    "jaw_symmetry": 0.8,
                                    "raw_angle": 4.0,
                                },
                            },
                            identity
                            | {
                                "review_id": "r2",
                                "measurements": {
                                    "head_axis_consistency": 0.7,
                                    "jaw_symmetry": 0.6,
                                    "raw_angle": 2.0,
                                },
                            },
                        ],
                    }
                ],
            }
        ],
    }


def test_progress_defaults_to_plain_trends_and_raw_normalized_values():
    rendered = _module().format_progress(_snapshot())
    assert "Attempts: 1 · Reviews: 2" in rendered
    assert "Improved: head axis consistency" in rendered
    assert "Needs attention: jaw symmetry" in rendered
    assert "head axis consistency: 0.70" in rendered
    assert "raw angle" not in rendered


def test_raw_values_can_be_hidden_and_disabled_retention_is_explicit():
    module = _module()
    assert "normalized measurements" not in module.format_progress(_snapshot(), False)
    assert module.format_progress({"retain_learning_progress": False}) == (
        "Learning-progress retention is disabled for this project."
    )
