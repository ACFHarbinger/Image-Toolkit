"""Storage-neutral domain model for artwork projects and learning progress."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

CURRENT_SCHEMA_VERSION = 1


def migrate_project_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic current-schema copy of a legacy manifest.

    Version 0 was the pre-release prototype shape. It never generated missing
    identity or timestamp values during migration, keeping repeated migrations
    byte-for-byte deterministic.
    """
    migrated = deepcopy(payload)
    version = migrated.get("schema_version", 0)
    if version == CURRENT_SCHEMA_VERSION:
        return migrated
    if version != 0:
        raise ValueError(f"unsupported project schema version: {version}")
    migrated["schema_version"] = 1
    migrated["consent"] = {
        "retain_artwork_in_history": migrated.pop("keep_artwork_history", False),
        "contribute_to_global_profile": False,
    }
    migrated["autosave"] = {
        "enabled": True,
        "recovery_revisions": migrated.pop("recovery_revisions", 10),
    }
    migrated["progress"] = {"exercises": migrated.pop("exercises", [])}
    return migrated


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id() -> str:
    return str(uuid4())


@dataclass(slots=True)
class Consent:
    """Privacy choices; personalized retention is disabled by default."""

    retain_artwork_in_history: bool = False
    contribute_to_global_profile: bool = False


@dataclass(slots=True)
class AutosavePolicy:
    """User-selectable recovery policy with bounded history by default."""

    enabled: bool = True
    recovery_revisions: int = 10

    def __post_init__(self) -> None:
        if self.recovery_revisions < 1:
            raise ValueError("recovery_revisions must be at least 1")


@dataclass(slots=True)
class Feedback:
    """One tutor observation attached to an exercise attempt."""

    category: str
    explanation: str
    score: float | None = None
    redline_asset: str | None = None


@dataclass(slots=True)
class Attempt:
    """One completed or in-progress exercise attempt."""

    exercise_id: str
    id: str = field(default_factory=_id)
    started_at: str = field(default_factory=_now)
    completed_at: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    feedback: list[Feedback] = field(default_factory=list)
    artwork_asset: str | None = None


@dataclass(slots=True)
class ExerciseProgress:
    """Project-local history for one curriculum exercise."""

    exercise_id: str
    attempts: list[Attempt] = field(default_factory=list)


@dataclass(slots=True)
class ProjectProgress:
    """Learning metrics that travel with their portable project."""

    exercises: list[ExerciseProgress] = field(default_factory=list)


@dataclass(slots=True)
class Project:
    """Portable project manifest; artwork files live beside this manifest."""

    title: str
    id: str = field(default_factory=_id)
    schema_version: int = CURRENT_SCHEMA_VERSION
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    consent: Consent = field(default_factory=Consent)
    autosave: AutosavePolicy = field(default_factory=AutosavePolicy)
    progress: ProjectProgress = field(default_factory=ProjectProgress)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation after privacy validation."""
        self.validate()
        return asdict(self)

    def validate(self) -> None:
        """Reject unsupported versions and artwork retention without consent."""
        if self.schema_version != CURRENT_SCHEMA_VERSION:
            raise ValueError(f"unsupported project schema version: {self.schema_version}")
        if not self.title.strip():
            raise ValueError("project title must not be empty")
        if not self.consent.retain_artwork_in_history:
            for exercise in self.progress.exercises:
                for attempt in exercise.attempts:
                    if attempt.artwork_asset or any(
                        item.redline_asset for item in attempt.feedback
                    ):
                        raise ValueError("artwork history requires explicit retention consent")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Project:
        """Validate and deserialize a project manifest."""
        payload = migrate_project_payload(payload)
        version = payload.get("schema_version")
        if version != CURRENT_SCHEMA_VERSION:
            raise ValueError(f"unsupported project schema version: {version}")
        consent = Consent(**payload.get("consent", {}))
        autosave = AutosavePolicy(**payload.get("autosave", {}))
        exercises = []
        for raw_exercise in payload.get("progress", {}).get("exercises", []):
            attempts = []
            for raw_attempt in raw_exercise.get("attempts", []):
                feedback = [Feedback(**item) for item in raw_attempt.get("feedback", [])]
                attempts.append(Attempt(**(raw_attempt | {"feedback": feedback})))
            exercises.append(ExerciseProgress(raw_exercise["exercise_id"], attempts))
        project = cls(
            title=payload["title"],
            id=payload["id"],
            schema_version=version,
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            consent=consent,
            autosave=autosave,
            progress=ProjectProgress(exercises),
        )
        project.validate()
        return project


@dataclass(slots=True)
class LearnerProfile:
    """Optional cross-project aggregates, stored separately from projects."""

    schema_version: int = CURRENT_SCHEMA_VERSION
    aggregate_metrics: dict[str, float] = field(default_factory=dict)
    contributing_project_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        if self.schema_version != CURRENT_SCHEMA_VERSION:
            raise ValueError(f"unsupported profile schema version: {self.schema_version}")
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LearnerProfile:
        """Validate and deserialize a learner profile."""
        profile = cls(**payload)
        profile.to_dict()
        return profile
