"""Storage-neutral learning-domain contracts shared by every host."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

LEARNING_SCHEMA_VERSION = 1


class EvidenceSource(StrEnum):
    GEOMETRY = "geometry"
    HEURISTIC = "heuristic"
    MODEL = "model"


class AutomationLevel(StrEnum):
    MANUAL = "manual"
    SUGGEST = "suggest"
    GUIDED = "guided"


class ModelTrust(StrEnum):
    BUILT_IN = "built_in"
    COMMUNITY = "community"
    UNVERIFIED = "unverified"


@dataclass(slots=True)
class RubricDimension:
    id: str
    title: str
    explanation: str
    minimum: float = 0.0
    maximum: float = 1.0


@dataclass(slots=True)
class Rubric:
    id: str
    version: str
    dimensions: list[RubricDimension]


@dataclass(slots=True)
class Exercise:
    id: str
    version: str
    method_id: str
    rubric_id: str
    title: str
    instructions: list[str]
    completion_criteria: list[str]


@dataclass(slots=True)
class Lesson:
    id: str
    version: str
    method_id: str
    title: str
    summary: str
    exercise_ids: list[str]
    schema_version: int = LEARNING_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    def validate(self) -> None:
        if self.schema_version != LEARNING_SCHEMA_VERSION:
            raise ValueError(f"unsupported learning schema version: {self.schema_version}")
        for label, value in (
            ("id", self.id),
            ("version", self.version),
            ("method_id", self.method_id),
        ):
            if not value.strip():
                raise ValueError(f"lesson {label} must not be empty")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Lesson:
        lesson = cls(**payload)
        lesson.validate()
        return lesson


@dataclass(slots=True)
class Evidence:
    region: tuple[float, float, float, float]
    source: EvidenceSource
    confidence: float
    observation: str

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if len(self.region) != 4 or any(value < 0 or value > 1 for value in self.region):
            raise ValueError("region must contain four normalized coordinates")


@dataclass(slots=True)
class Redline:
    layer_name: str
    geometry: list[tuple[float, float]]
    explanation: str


@dataclass(slots=True)
class Suggestion:
    id: str
    title: str
    preview_layer_name: str
    accepted: bool | None = None


@dataclass(slots=True)
class Review:
    id: str
    exercise_id: str
    exercise_version: str
    method_id: str
    rubric_id: str
    rubric_version: str
    evidence: list[Evidence]
    explanations: list[str]
    redlines: list[Redline] = field(default_factory=list)
    suggestions: list[Suggestion] = field(default_factory=list)
    measurements: dict[str, float] = field(default_factory=dict)
    targeted_exercise_ids: list[str] = field(default_factory=list)
    schema_version: int = LEARNING_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        if self.schema_version != LEARNING_SCHEMA_VERSION:
            raise ValueError(f"unsupported learning schema version: {self.schema_version}")
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Review:
        evidence = [Evidence(**item) for item in payload.get("evidence", [])]
        redlines = [Redline(**item) for item in payload.get("redlines", [])]
        suggestions = [Suggestion(**item) for item in payload.get("suggestions", [])]
        return cls(
            **(payload | {"evidence": evidence, "redlines": redlines, "suggestions": suggestions})
        )


@dataclass(slots=True)
class ArtistFeedback:
    review_id: str
    helpful: bool | None = None
    incorrect: bool = False
    not_applicable: bool = False
    note: str | None = None


@dataclass(slots=True)
class TutorSettings:
    retain_progress: bool = False
    retain_artwork: bool = False
    allow_optional_models: bool = False
    automation_level: AutomationLevel = AutomationLevel.SUGGEST
    review_shortcut: str = "Ctrl+Shift+R"
    accept_shortcut: str = "Tab"
    reject_shortcut: str = "Esc"


@dataclass(slots=True)
class LocalModel:
    id: str
    version: str
    path: str
    trust: ModelTrust = ModelTrust.UNVERIFIED
    enabled: bool = False


@dataclass(slots=True)
class ModelRegistry:
    models: list[LocalModel] = field(default_factory=list)

    def register(self, model: LocalModel) -> None:
        if any(item.id == model.id and item.version == model.version for item in self.models):
            raise ValueError(f"model already registered: {model.id}@{model.version}")
        self.models.append(model)
