"""Tests for versioned tutor contracts and privacy defaults."""

import pytest

from learning import (
    Evidence,
    EvidenceSource,
    Lesson,
    LocalModel,
    ModelRegistry,
    ModelTrust,
    Review,
    TutorSettings,
)


def test_lesson_round_trip_preserves_method_and_version():
    lesson = Lesson("front-head", "1.0", "anime-head-v1", "Front Head", "Basics", ["ex-1"])
    assert Lesson.from_dict(lesson.to_dict()) == lesson


def test_review_round_trip_preserves_structured_evidence():
    review = Review(
        "review-1",
        "ex-1",
        "1.0",
        "anime-head-v1",
        "head-rubric",
        "1.0",
        [Evidence((0.1, 0.2, 0.5, 0.6), EvidenceSource.GEOMETRY, 0.8, "Eye line tilts")],
        ["Align both eyes to the construction eye-line."],
    )
    assert Review.from_dict(review.to_dict()) == review


def test_confidence_and_region_are_validated():
    with pytest.raises(ValueError, match="confidence"):
        Evidence((0, 0, 1, 1), EvidenceSource.MODEL, 1.2, "bad")
    with pytest.raises(ValueError, match="normalized"):
        Evidence((0, 0, 2, 1), EvidenceSource.GEOMETRY, 0.5, "bad")


def test_privacy_sensitive_settings_default_off():
    settings = TutorSettings()
    assert not settings.retain_progress
    assert not settings.retain_artwork
    assert not settings.allow_optional_models
    assert settings.accept_shortcut == ""


def test_model_registry_requires_explicit_unique_records():
    registry = ModelRegistry()
    model = LocalModel("landmarks", "1", "/models/landmarks", ModelTrust.COMMUNITY)
    registry.register(model)
    assert not model.enabled
    with pytest.raises(ValueError, match="already registered"):
        registry.register(model)
