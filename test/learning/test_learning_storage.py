"""Tests for atomic, migrated learning-catalog persistence."""

import json

import pytest

from cel_shaded_generator.learning import (
    Exercise,
    LearningCatalog,
    Lesson,
    LocalModel,
    ModelRegistry,
    ModelTrust,
    Rubric,
    RubricDimension,
    load_catalog,
    save_catalog,
)


def _catalog():
    return LearningCatalog(
        lessons=[Lesson("lesson", "1", "anime-head-v1", "Head", "Intro", ["exercise"])],
        exercises=[
            Exercise("exercise", "1", "anime-head-v1", "rubric", "Circle", ["Draw"], ["Done"])
        ],
        rubrics=[Rubric("rubric", "1", [RubricDimension("axis", "Axis", "Aligned")])],
        model_registry=ModelRegistry(
            [LocalModel("landmarks", "1", "/local/model", ModelTrust.COMMUNITY)]
        ),
    )


def test_catalog_round_trip_preserves_types_and_privacy_defaults(tmp_path):
    catalog = _catalog()
    path = save_catalog(tmp_path / "catalog.json", catalog)
    loaded = load_catalog(path)
    assert loaded == catalog
    assert not loaded.settings.retain_progress
    assert not loaded.settings.retain_artwork
    assert loaded.model_registry.models[0].trust is ModelTrust.COMMUNITY


def test_version_zero_migration_is_deterministic_and_private():
    legacy = {"lessons": [], "exercises": [], "rubrics": [], "settings": {}}
    first = LearningCatalog.from_dict(legacy)
    second = LearningCatalog.from_dict(legacy)
    assert first == second
    assert not first.settings.retain_progress
    assert first.model_registry.models == []


def test_future_catalog_version_is_rejected(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schema_version": 999}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported learning schema"):
        load_catalog(path)
