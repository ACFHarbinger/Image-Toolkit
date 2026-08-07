"""Tests for deterministic curriculum progression and remediation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from learning import (
    CurriculumStep,
    build_curriculum_v1,
    compare_attempts,
    next_primary_exercise,
    recommend_remediation,
)
from learning.model import Review


def _review(**measurements: float) -> Review:
    return Review(
        id="review-1",
        exercise_id="anime-head-front-construction",
        exercise_version="1.0.0",
        method_id="anime-head-construction-v1",
        rubric_id="anime-head-front-structure",
        rubric_version="1.0.0",
        evidence=[],
        explanations=[],
        measurements=measurements,
    )


def test_curriculum_v1_has_stable_complete_primary_sequence() -> None:
    curriculum = build_curriculum_v1()

    assert curriculum.id == "anime-head-and-face-v1"
    assert curriculum.version == "1.0.0"
    assert len(curriculum.steps) == 9
    assert len(curriculum.exercises) == 17
    assert {
        "cel-value-mask-consolidation",
        "cel-value-island-audit",
        "cel-value-light-transfer",
        "cel-value-third-value-restraint",
    }.issubset({exercise.id for exercise in curriculum.exercises})
    assert next_primary_exercise(curriculum, set()) == "anime-head-front-construction"

    completed = {step.exercise_id for step in curriculum.steps[:4]}
    assert next_primary_exercise(curriculum, completed) == "anime-head-features"
    assert (
        next_primary_exercise(curriculum, {step.exercise_id for step in curriculum.steps}) is None
    )


def test_progression_rejects_unknown_completion_and_forward_prerequisite() -> None:
    curriculum = build_curriculum_v1()
    with pytest.raises(ValueError, match="unknown curriculum step"):
        next_primary_exercise(curriculum, {"unknown"})

    invalid = replace(
        curriculum,
        steps=(CurriculumStep("anime-head-front-construction", ("anime-head-orientation",)),),
    )
    with pytest.raises(ValueError, match="earlier curriculum steps"):
        invalid.validate()


def test_weakest_failed_dimension_selects_explainable_remediation() -> None:
    recommendation = recommend_remediation(
        build_curriculum_v1(),
        {
            "head_axis_consistency": 0.60,
            "eye_line_consistency": 0.20,
            "chin_centering": 0.90,
        },
    )

    assert recommendation is not None
    assert recommendation.dimension_id == "eye_line_consistency"
    assert recommendation.exercise_id == "anime-head-front-axis-practice"
    assert "0.20" in recommendation.explanation
    assert "0.75" in recommendation.explanation


def test_remediation_ties_are_stable_and_missing_evidence_is_not_failure() -> None:
    curriculum = build_curriculum_v1()
    recommendation = recommend_remediation(
        curriculum, {"head_axis_consistency": 0.5, "eye_line_consistency": 0.5}
    )

    assert recommendation is not None
    assert recommendation.dimension_id == "head_axis_consistency"
    assert recommend_remediation(curriculum, {}) is None
    assert recommend_remediation(curriculum, {"head_axis_consistency": 0.8}) is None


def test_remediation_rejects_invalid_normalized_measurement() -> None:
    with pytest.raises(ValueError, match="between zero and one"):
        recommend_remediation(build_curriculum_v1(), {"head_axis_consistency": 1.1})


def test_comparable_attempts_report_direction_of_change() -> None:
    before = _review(
        head_axis_consistency=0.4,
        eye_line_consistency=0.7,
        chin_centering=0.8,
    )
    after = _review(
        head_axis_consistency=0.8,
        eye_line_consistency=0.6,
        chin_centering=0.8,
    )

    comparison = compare_attempts(before, after)

    assert comparison.improved == ("head_axis_consistency",)
    assert comparison.declined == ("eye_line_consistency",)
    assert comparison.unchanged == ("chin_centering",)
    assert comparison.deltas["head_axis_consistency"] == pytest.approx(0.4)


@pytest.mark.parametrize("field", ["exercise_version", "method_id", "rubric_version"])
def test_incompatible_attempt_versions_are_never_compared(field: str) -> None:
    before = _review(head_axis_consistency=0.4)
    after = replace(before, id="review-2", **{field: "other-version"})

    with pytest.raises(ValueError, match="incompatible"):
        compare_attempts(before, after)


def test_comparison_requires_shared_normalized_scores() -> None:
    with pytest.raises(ValueError, match="no shared normalized rubric scores"):
        compare_attempts(_review(raw_angle=3.0), _review(raw_angle=2.0))
