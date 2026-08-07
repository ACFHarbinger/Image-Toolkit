"""Deterministic curriculum progression and remediation for the learning alpha."""

from __future__ import annotations

from dataclasses import dataclass

from .model import Exercise, Lesson, Review, Rubric, RubricDimension

CURRICULUM_ID = "anime-head-and-face-v1"
CURRICULUM_VERSION = "1.0.0"
METHOD_ID = "anime-head-construction-v1"
RUBRIC_ID = "anime-head-construction"
RUBRIC_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class CurriculumStep:
    """One ordered primary exercise and its explicit prerequisites."""

    exercise_id: str
    prerequisite_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RemediationRule:
    """Explainable mapping from one normalized skill score to focused practice."""

    dimension_id: str
    threshold: float
    exercise_id: str
    reason: str
    priority: int

    def __post_init__(self) -> None:
        if not 0 <= self.threshold <= 1:
            raise ValueError("remediation threshold must be between zero and one")
        if not self.reason.strip():
            raise ValueError("remediation reason must not be empty")


@dataclass(frozen=True, slots=True)
class Curriculum:
    """Versioned offline teaching content with deterministic routing rules."""

    id: str
    version: str
    method_id: str
    lessons: tuple[Lesson, ...]
    exercises: tuple[Exercise, ...]
    rubrics: tuple[Rubric, ...]
    steps: tuple[CurriculumStep, ...]
    remediation_rules: tuple[RemediationRule, ...]

    def validate(self) -> None:
        """Reject ambiguous identifiers, dangling links, and cyclic ordering."""
        for label, value in (
            ("id", self.id),
            ("version", self.version),
            ("method", self.method_id),
        ):
            if not value.strip():
                raise ValueError(f"curriculum {label} must not be empty")
        _require_unique("lesson", [item.id for item in self.lessons])
        _require_unique("exercise", [item.id for item in self.exercises])
        _require_unique("rubric", [item.id for item in self.rubrics])
        _require_unique("step", [item.exercise_id for item in self.steps])

        exercise_ids = {item.id for item in self.exercises}
        rubric_ids = {item.id for item in self.rubrics}
        seen_steps: set[str] = set()
        for exercise in self.exercises:
            if exercise.method_id != self.method_id:
                raise ValueError("exercise method does not match its curriculum")
            if exercise.rubric_id not in rubric_ids:
                raise ValueError(f"exercise references unknown rubric: {exercise.rubric_id}")
        for lesson in self.lessons:
            if lesson.method_id != self.method_id:
                raise ValueError("lesson method does not match its curriculum")
            if not set(lesson.exercise_ids) <= exercise_ids:
                raise ValueError(f"lesson references an unknown exercise: {lesson.id}")
        for step in self.steps:
            if step.exercise_id not in exercise_ids:
                raise ValueError(f"step references unknown exercise: {step.exercise_id}")
            if not set(step.prerequisite_ids) <= seen_steps:
                raise ValueError("step prerequisites must refer to earlier curriculum steps")
            seen_steps.add(step.exercise_id)
        dimension_ids = {dimension.id for rubric in self.rubrics for dimension in rubric.dimensions}
        for rule in self.remediation_rules:
            if rule.dimension_id not in dimension_ids:
                raise ValueError(f"rule references unknown dimension: {rule.dimension_id}")
            if rule.exercise_id not in exercise_ids:
                raise ValueError(f"rule references unknown exercise: {rule.exercise_id}")


@dataclass(frozen=True, slots=True)
class RemediationRecommendation:
    exercise_id: str
    dimension_id: str
    measured_score: float
    threshold: float
    explanation: str


@dataclass(frozen=True, slots=True)
class AttemptComparison:
    """Direction-of-change scores for two strictly comparable reviews."""

    exercise_id: str
    deltas: dict[str, float]
    improved: tuple[str, ...]
    unchanged: tuple[str, ...]
    declined: tuple[str, ...]


def next_primary_exercise(curriculum: Curriculum, completed_ids: set[str]) -> str | None:
    """Return the first unlocked incomplete primary exercise, or ``None``."""
    curriculum.validate()
    known = {step.exercise_id for step in curriculum.steps}
    if not completed_ids <= known:
        raise ValueError("completed exercises contain an unknown curriculum step")
    for step in curriculum.steps:
        if step.exercise_id not in completed_ids and set(step.prerequisite_ids) <= completed_ids:
            return step.exercise_id
    return None


def recommend_remediation(
    curriculum: Curriculum, measurements: dict[str, float]
) -> RemediationRecommendation | None:
    """Select the weakest failing score with stable priority tie-breaking."""
    curriculum.validate()
    candidates: list[tuple[float, int, str, RemediationRule]] = []
    for rule in curriculum.remediation_rules:
        score = measurements.get(rule.dimension_id)
        if score is None:
            continue
        if not isinstance(score, (int, float)) or not 0 <= score <= 1:
            raise ValueError(f"measurement {rule.dimension_id} must be between zero and one")
        if score < rule.threshold:
            candidates.append((score / rule.threshold, rule.priority, rule.dimension_id, rule))
    if not candidates:
        return None
    _, _, _, rule = min(candidates)
    score = float(measurements[rule.dimension_id])
    return RemediationRecommendation(
        exercise_id=rule.exercise_id,
        dimension_id=rule.dimension_id,
        measured_score=score,
        threshold=rule.threshold,
        explanation=(
            f"{rule.reason} The measured {rule.dimension_id.replace('_', ' ')} score was "
            f"{score:.2f}, below the {rule.threshold:.2f} practice threshold."
        ),
    )


def compare_attempts(
    before: Review, after: Review, *, tolerance: float = 1e-6
) -> AttemptComparison:
    """Compare normalized scores only when method and rubric identities match."""
    if tolerance < 0:
        raise ValueError("comparison tolerance must not be negative")
    identity_before = (
        before.exercise_id,
        before.exercise_version,
        before.method_id,
        before.rubric_id,
        before.rubric_version,
    )
    identity_after = (
        after.exercise_id,
        after.exercise_version,
        after.method_id,
        after.rubric_id,
        after.rubric_version,
    )
    if identity_before != identity_after:
        raise ValueError("attempts use incompatible exercise, method, or rubric versions")
    shared = sorted(set(before.measurements) & set(after.measurements))
    score_ids = [
        item
        for item in shared
        if item.endswith("_consistency") or item in {"chin_centering", "jaw_symmetry"}
    ]
    if not score_ids:
        raise ValueError("attempts have no shared normalized rubric scores")
    deltas = {
        item: float(after.measurements[item] - before.measurements[item]) for item in score_ids
    }
    improved = tuple(item for item, delta in deltas.items() if delta > tolerance)
    declined = tuple(item for item, delta in deltas.items() if delta < -tolerance)
    unchanged = tuple(item for item, delta in deltas.items() if abs(delta) <= tolerance)
    return AttemptComparison(before.exercise_id, deltas, improved, unchanged, declined)


def build_curriculum_v1() -> Curriculum:
    """Build the immutable English curriculum shipped with the first alpha."""
    dimensions = [
        RubricDimension(
            "head_axis_consistency", "Head axis", "Keep the construction axis intentional."
        ),
        RubricDimension(
            "eye_line_consistency", "Eye-line", "Relate the eye-line to the head orientation."
        ),
        RubricDimension(
            "chin_centering", "Chin placement", "Place the chin consistently on the facial axis."
        ),
        RubricDimension(
            "jaw_symmetry", "Jaw structure", "Control the jaw taper before adding details."
        ),
        RubricDimension(
            "perspective_compression", "Perspective", "Compress far-side forms consistently."
        ),
        RubricDimension(
            "feature_placement", "Feature placement", "Place features from construction guides."
        ),
        RubricDimension(
            "value_grouping", "Value grouping", "Separate light and shadow into readable groups."
        ),
    ]
    rubric = Rubric(RUBRIC_ID, RUBRIC_VERSION, dimensions)
    definitions = (
        (
            "anime-head-front-construction",
            "Front construction",
            "Build a front head from circle, axes, jaw, and chin.",
        ),
        (
            "anime-head-orientation",
            "Head orientation",
            "Construct front, profile, and three-quarter orientations.",
        ),
        (
            "anime-head-volume-jaw",
            "Cranium and jaw variation",
            "Vary proportion without losing perspective.",
        ),
        (
            "anime-head-eyes",
            "Eye placement",
            "Place and compress eyes using the construction guides.",
        ),
        (
            "anime-head-features",
            "Facial landmarks",
            "Place nose, mouth, ears, and hairline structurally.",
        ),
        (
            "anime-head-asymmetry",
            "Intentional asymmetry",
            "Distinguish deliberate asymmetry from drift.",
        ),
        (
            "anime-head-variation",
            "Feature variation",
            "Vary features while preserving the construction.",
        ),
        (
            "anime-head-cel-values",
            "Two-tone values",
            "Group head lighting into clear light and shadow.",
        ),
        (
            "anime-head-review",
            "Combined review",
            "Combine construction, features, and simple shading.",
        ),
        (
            "anime-head-front-axis-practice",
            "Axis practice",
            "Repeat axes and jaw placement without details.",
        ),
        (
            "anime-head-perspective-practice",
            "Perspective practice",
            "Repeat turned heads with far-side compression.",
        ),
        (
            "anime-head-feature-placement-practice",
            "Feature placement practice",
            "Place features on prepared guides.",
        ),
        (
            "anime-head-value-practice",
            "Value grouping practice",
            "Reduce references to two value shapes.",
        ),
    )
    exercises = tuple(
        Exercise(
            id=identifier,
            version="1.0.0",
            method_id=METHOD_ID,
            rubric_id=RUBRIC_ID,
            title=title,
            instructions=[instruction],
            completion_criteria=["Complete the prompt without tracing a previous attempt."],
        )
        for identifier, title, instruction in definitions
    )
    primary_ids = tuple(identifier for identifier, _, _ in definitions[:9])
    lesson = Lesson(
        id=CURRICULUM_ID,
        version=CURRICULUM_VERSION,
        method_id=METHOD_ID,
        title="Anime Head and Face Construction",
        summary="A beginner sequence from construction axes to a simply cel-shaded head.",
        exercise_ids=list(primary_ids),
    )
    steps = tuple(
        CurriculumStep(identifier, () if index == 0 else (primary_ids[index - 1],))
        for index, identifier in enumerate(primary_ids)
    )
    rules = (
        RemediationRule(
            "head_axis_consistency",
            0.75,
            "anime-head-front-axis-practice",
            "Practice the large construction axes before adding features.",
            0,
        ),
        RemediationRule(
            "eye_line_consistency",
            0.75,
            "anime-head-front-axis-practice",
            "Practice perpendicular center- and eye-lines before adding features.",
            1,
        ),
        RemediationRule(
            "chin_centering",
            0.75,
            "anime-head-front-axis-practice",
            "Practice carrying the facial axis through to the chin.",
            2,
        ),
        RemediationRule(
            "jaw_symmetry",
            0.75,
            "anime-head-front-axis-practice",
            "Practice comparing the two large jaw tapers.",
            3,
        ),
        RemediationRule(
            "perspective_compression",
            0.70,
            "anime-head-perspective-practice",
            "Practice the near- and far-side relationship on turned heads.",
            4,
        ),
        RemediationRule(
            "feature_placement",
            0.70,
            "anime-head-feature-placement-practice",
            "Practice placing landmarks on prepared construction guides.",
            5,
        ),
        RemediationRule(
            "value_grouping",
            0.70,
            "anime-head-value-practice",
            "Practice designing one readable shadow group before rendering.",
            6,
        ),
    )
    curriculum = Curriculum(
        CURRICULUM_ID,
        CURRICULUM_VERSION,
        METHOD_ID,
        (lesson,),
        exercises,
        (rubric,),
        steps,
        rules,
    )
    curriculum.validate()
    return curriculum


def _require_unique(label: str, values: list[str]) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"curriculum {label} identifiers must be unique")
