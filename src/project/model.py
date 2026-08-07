"""Storage-neutral domain model for artwork projects and learning progress."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

CURRENT_SCHEMA_VERSION = 14


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
    if version not in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13):
        raise ValueError(f"unsupported project schema version: {version}")
    if version == 0:
        migrated["consent"] = {
            "retain_artwork_in_history": migrated.pop("keep_artwork_history", False),
            "contribute_to_global_profile": False,
        }
        migrated["autosave"] = {
            "enabled": True,
            "recovery_revisions": migrated.pop("recovery_revisions", 10),
        }
        migrated["progress"] = {"exercises": migrated.pop("exercises", [])}
    for exercise in migrated.get("progress", {}).get("exercises", []):
        for attempt in exercise.get("attempts", []):
            attempt.setdefault("reviews", [])
            for review in attempt["reviews"]:
                review.setdefault("suggestion_decision_rationale", None)
                review.setdefault("suggestion_decision_rationale_updated_at", None)
                review.setdefault("suggestion_decision_rationale_history", [])
                review.setdefault("source_attempt_id", None)
                review.setdefault("source_review_id", None)
                review.setdefault("artist_feedback", None)
                if review["artist_feedback"] is not None:
                    review["artist_feedback"].setdefault("revision", 1)
                review.setdefault("artist_feedback_history", [])
    migrated.setdefault("consent", {}).setdefault("retain_learning_progress", True)
    migrated.setdefault(
        "feedback_policy",
        {"retain_revision_history": False, "note_character_limit": 2000},
    )
    migrated.setdefault("identity_card_policy", {"retain_revision_history": False})
    migrated.setdefault("capstone_policy", {"retain_rationale_history": False})
    migrated.setdefault("identity_card", None)
    migrated.setdefault("identity_card_history", [])
    migrated.setdefault("style_bible_assets", [])
    migrated.setdefault("correspondence_set_assets", [])
    migrated.setdefault("editor_document_assets", [])
    migrated.setdefault("study_consent", {})
    migrated.setdefault("study_sessions", [])
    migrated.setdefault("chapter_pages", [])
    migrated.setdefault("signal_weights", {})
    migrated["schema_version"] = CURRENT_SCHEMA_VERSION
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
    retain_learning_progress: bool = True


@dataclass(slots=True)
class AutosavePolicy:
    """User-selectable recovery policy with bounded history by default."""

    enabled: bool = True
    recovery_revisions: int = 10

    def __post_init__(self) -> None:
        if self.recovery_revisions < 1:
            raise ValueError("recovery_revisions must be at least 1")


@dataclass(slots=True)
class FeedbackPolicy:
    """Project-local policy for editable advice reports."""

    retain_revision_history: bool = False
    note_character_limit: int = 2000

    def __post_init__(self) -> None:
        if not isinstance(self.retain_revision_history, bool):
            raise ValueError("feedback revision-history setting must be boolean")
        if (
            not isinstance(self.note_character_limit, int)
            or not 1 <= self.note_character_limit <= 100_000
        ):
            raise ValueError("feedback note limit must be between 1 and 100000 characters")


@dataclass(slots=True)
class IdentityCardPolicy:
    """Project-local edit-history choice for the selected character specification."""

    retain_revision_history: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.retain_revision_history, bool):
            raise ValueError("identity-card revision-history setting must be boolean")


@dataclass(slots=True)
class CapstonePolicy:
    """Project-local retention choice for edited capstone rationales."""

    retain_rationale_history: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.retain_rationale_history, bool):
            raise ValueError("capstone rationale-history setting must be boolean")


@dataclass(slots=True)
class IdentityAnchor:
    """One normalized structural relationship plus its artist-facing explanation."""

    key: str
    value: float
    description: str

    def __post_init__(self) -> None:
        if not self.key.strip() or not self.description.strip():
            raise ValueError("identity-anchor key and description must not be empty")
        if not isinstance(self.value, (int, float)) or not 0 <= self.value <= 1:
            raise ValueError("identity-anchor value must be normalized between zero and one")


@dataclass(slots=True)
class IdentityCard:
    """Editable five-to-eight-anchor identity specification for one selected character."""

    name: str
    anchors: list[IdentityAnchor]
    revision: int = 1

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("identity-card name must not be empty")
        if not 5 <= len(self.anchors) <= 8:
            raise ValueError("identity card requires five to eight anchors")
        keys = [anchor.key for anchor in self.anchors]
        if len(keys) != len(set(keys)):
            raise ValueError("identity-anchor keys must be unique")
        if self.revision < 1:
            raise ValueError("identity-card revision must be positive")


@dataclass(slots=True)
class Feedback:
    """One tutor observation attached to an exercise attempt."""

    category: str
    explanation: str
    score: float | None = None
    redline_asset: str | None = None


class SuggestionDecision(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class AdviceRating(StrEnum):
    HELPFUL = "helpful"
    UNHELPFUL = "unhelpful"
    INCORRECT = "incorrect"
    NOT_APPLICABLE = "not_applicable"


@dataclass(slots=True)
class AdviceFeedback:
    """One explicit artist judgment stored with its reviewed attempt."""

    rating: AdviceRating
    note: str | None = None
    revision: int = 1

    def __post_init__(self) -> None:
        if self.note is not None and not self.note.strip():
            raise ValueError("advice feedback note must be absent or non-empty")
        if self.revision < 1:
            raise ValueError("advice feedback revision must be positive")


@dataclass(slots=True)
class StudyConsent:
    """Explicit, revocable opt-in for the beginner alpha study protocol.

    Roadmap A4 (issue #14) is gated on live checks being intentionally
    scheduled; this record only stores an artist's explicit choice to
    participate once that happens. It never opts a project in implicitly.
    """

    opted_in: bool = False
    consent_version: int = 1
    consented_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.opted_in, bool):
            raise ValueError("study-consent opt-in must be boolean")
        if self.consent_version < 1:
            raise ValueError("study-consent version must be positive")
        if self.opted_in and (self.consented_at is None or not self.consented_at.strip()):
            raise ValueError("opted-in consent requires a consent timestamp")
        if not self.opted_in and self.consented_at is not None:
            raise ValueError("withdrawn consent must not retain a consent timestamp")


@dataclass(slots=True)
class StudySession:
    """One baseline/review/remedial/redraw protocol instance (roadmap A4).

    Stores only attempt/exercise identifiers and an explanation-usefulness
    rating -- never a global artist score, matching the roadmap's rule that
    comparisons are per-rubric and never ranked.
    """

    id: str
    baseline_attempt_id: str
    remedial_exercise_id: str | None = None
    redraw_attempt_id: str | None = None
    explanation_rating: AdviceRating | None = None
    completed_at: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.baseline_attempt_id.strip():
            raise ValueError("study-session id and baseline attempt id must not be empty")
        if self.remedial_exercise_id is not None and not self.remedial_exercise_id.strip():
            raise ValueError("study-session remedial exercise id must be absent or non-empty")
        if self.redraw_attempt_id is not None and not self.redraw_attempt_id.strip():
            raise ValueError("study-session redraw attempt id must be absent or non-empty")


class PageStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"


@dataclass(slots=True)
class ChapterPage:
    """One page in a batch chapter review queue (roadmap milestone 6).

    Execution-agnostic: a page may be segmented/assigned interactively in
    Krita or, in a later slice, by an offline batch tool -- this record only
    tracks queue position and review status, never how a page reached it.
    Each page is independently segmented and corresponded (no cross-page
    correspondence inference); ``panel_id`` is the existing
    ``RegionCorrespondence`` panel-scoping field, letting every page in one
    chapter share a single correspondence set without regions colliding
    across pages.
    """

    id: str
    document_asset: str
    panel_id: str
    status: PageStatus = PageStatus.PENDING
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("chapter-page id must not be empty")
        if not self.panel_id.strip():
            raise ValueError("chapter-page panel id must not be empty")
        path = PurePosixPath(self.document_asset)
        if (
            not self.document_asset.strip()
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in self.document_asset
        ):
            raise ValueError("chapter-page document asset must be a safe relative POSIX path")
        if self.notes is not None and not self.notes.strip():
            raise ValueError("chapter-page notes must be absent or non-empty")


_WEIGHT_TOLERANCE = 1e-6


@dataclass(slots=True)
class SignalWeights:
    """Learned weights for ``colorization.confidence``'s deterministic
    correspondence-suggestion signals (roadmap milestone 4, issue #24).

    Not a trained model: a multiplicative-weights update after each
    explicit artist assignment nudges these two weights toward whichever
    signal (region-name/material-alias similarity, or adjacency agreement
    with already-assigned neighbors) would have predicted the artist's
    actual choice. Project-scoped rather than a portable/shareable asset,
    since it reflects one artist's own naming and workflow conventions.
    """

    adjacency_weight: float = 0.5
    name_weight: float = 0.5
    update_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.adjacency_weight, (int, float)) or not (
            0 <= self.adjacency_weight <= 1
        ):
            raise ValueError("adjacency weight must be between zero and one")
        if not isinstance(self.name_weight, (int, float)) or not 0 <= self.name_weight <= 1:
            raise ValueError("name weight must be between zero and one")
        if abs(self.adjacency_weight + self.name_weight - 1.0) > _WEIGHT_TOLERANCE:
            raise ValueError("signal weights must sum to one")
        if not isinstance(self.update_count, int) or self.update_count < 0:
            raise ValueError("signal-weight update count must be non-negative")


@dataclass(frozen=True, slots=True)
class RationaleRevision:
    text: str
    revised_at: str

    def __post_init__(self) -> None:
        if not self.text.strip() or not self.revised_at.strip():
            raise ValueError("rationale revision text and timestamp must not be empty")


@dataclass(slots=True)
class ReviewRecord:
    """Privacy-safe review result persisted without artwork pixels."""

    id: str
    exercise_version: str
    method_id: str
    rubric_id: str
    rubric_version: str
    measurements: dict[str, float]
    explanations: list[str]
    suggestion_decision: SuggestionDecision = SuggestionDecision.PENDING
    suggestion_decision_rationale: str | None = None
    suggestion_decision_rationale_updated_at: str | None = None
    suggestion_decision_rationale_history: list[RationaleRevision] = field(default_factory=list)
    source_attempt_id: str | None = None
    source_review_id: str | None = None
    artist_feedback: AdviceFeedback | None = None
    artist_feedback_history: list[AdviceFeedback] = field(default_factory=list)

    def __post_init__(self) -> None:
        for label, value in (
            ("review id", self.id),
            ("exercise version", self.exercise_version),
            ("method id", self.method_id),
            ("rubric id", self.rubric_id),
            ("rubric version", self.rubric_version),
        ):
            if not value.strip():
                raise ValueError(f"{label} must not be empty")
        if not all(isinstance(value, (int, float)) for value in self.measurements.values()):
            raise ValueError("review measurements must be numeric")

    @classmethod
    def from_review_payload(cls, payload: dict[str, Any]) -> ReviewRecord:
        """Extract only privacy-safe fields from an engine review response."""
        try:
            return cls(
                id=payload["id"],
                exercise_version=payload["exercise_version"],
                method_id=payload["method_id"],
                rubric_id=payload["rubric_id"],
                rubric_version=payload["rubric_version"],
                measurements=dict(payload.get("measurements", {})),
                explanations=list(payload.get("explanations", [])),
            )
        except (KeyError, TypeError) as error:
            raise ValueError("review payload is incomplete") from error

    def decide(
        self,
        decision: SuggestionDecision,
        rationale: str | None = None,
        updated_at: str | None = None,
    ) -> bool:
        """Finalize a pending decision; repeated identical decisions are idempotent."""
        if self.suggestion_decision is decision:
            return False
        if self.suggestion_decision is not SuggestionDecision.PENDING:
            raise ValueError("a finalized suggestion decision cannot be changed")
        if rationale is not None and not rationale.strip():
            raise ValueError("decision rationale must be absent or non-empty")
        self.suggestion_decision = decision
        self.suggestion_decision_rationale = rationale
        self.suggestion_decision_rationale_updated_at = (
            updated_at if rationale is not None else None
        )
        return True

    def revise_rationale(self, rationale: str, updated_at: str, policy: CapstonePolicy) -> bool:
        """Edit rationale text without changing the finalized artist decision."""
        if self.suggestion_decision is SuggestionDecision.PENDING:
            raise ValueError("a pending suggestion has no final rationale to revise")
        if not rationale.strip() or not updated_at.strip():
            raise ValueError("rationale and revision timestamp must not be empty")
        if rationale == self.suggestion_decision_rationale:
            return False
        if (
            policy.retain_rationale_history
            and self.suggestion_decision_rationale is not None
            and self.suggestion_decision_rationale_updated_at is not None
        ):
            self.suggestion_decision_rationale_history.append(
                RationaleRevision(
                    self.suggestion_decision_rationale,
                    self.suggestion_decision_rationale_updated_at,
                )
            )
        else:
            self.suggestion_decision_rationale_history.clear()
        self.suggestion_decision_rationale = rationale
        self.suggestion_decision_rationale_updated_at = updated_at
        return True

    def report_feedback(self, feedback: AdviceFeedback, policy: FeedbackPolicy) -> bool:
        """Create or revise feedback according to the project-local history policy."""
        if feedback.note is not None and len(feedback.note) > policy.note_character_limit:
            raise ValueError(
                f"advice feedback note exceeds the {policy.note_character_limit}-character limit"
            )
        if self.artist_feedback == feedback:
            return False
        if self.artist_feedback is not None:
            if (
                self.artist_feedback.rating is feedback.rating
                and self.artist_feedback.note == feedback.note
            ):
                return False
            if policy.retain_revision_history:
                self.artist_feedback_history.append(self.artist_feedback)
            else:
                self.artist_feedback_history.clear()
            feedback.revision = self.artist_feedback.revision + 1
        self.artist_feedback = feedback
        return True


@dataclass(slots=True)
class Attempt:
    """One completed or in-progress exercise attempt."""

    exercise_id: str
    id: str = field(default_factory=_id)
    started_at: str = field(default_factory=_now)
    completed_at: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    feedback: list[Feedback] = field(default_factory=list)
    reviews: list[ReviewRecord] = field(default_factory=list)
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
    document_asset: str | None = None
    consent: Consent = field(default_factory=Consent)
    autosave: AutosavePolicy = field(default_factory=AutosavePolicy)
    feedback_policy: FeedbackPolicy = field(default_factory=FeedbackPolicy)
    identity_card_policy: IdentityCardPolicy = field(default_factory=IdentityCardPolicy)
    capstone_policy: CapstonePolicy = field(default_factory=CapstonePolicy)
    identity_card: IdentityCard | None = None
    identity_card_history: list[IdentityCard] = field(default_factory=list)
    style_bible_assets: list[str] = field(default_factory=list)
    correspondence_set_assets: list[str] = field(default_factory=list)
    editor_document_assets: list[str] = field(default_factory=list)
    study_consent: StudyConsent = field(default_factory=StudyConsent)
    study_sessions: list[StudySession] = field(default_factory=list)
    chapter_pages: list[ChapterPage] = field(default_factory=list)
    signal_weights: SignalWeights = field(default_factory=SignalWeights)
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
        if self.document_asset is not None:
            path = PurePosixPath(self.document_asset)
            if path.is_absolute() or ".." in path.parts or "\\" in self.document_asset:
                raise ValueError("project document asset must be a safe relative path")
        if not self.consent.retain_artwork_in_history:
            for exercise in self.progress.exercises:
                for attempt in exercise.attempts:
                    if attempt.artwork_asset or any(
                        item.redline_asset for item in attempt.feedback
                    ):
                        raise ValueError("artwork history requires explicit retention consent")
        if not self.consent.retain_learning_progress and self.progress.exercises:
            raise ValueError("learning progress retention is disabled for this project")
        if not self.identity_card_policy.retain_revision_history and self.identity_card_history:
            raise ValueError("identity-card history exists while revision retention is disabled")
        if not self.capstone_policy.retain_rationale_history:
            if any(
                review.suggestion_decision_rationale_history
                for exercise in self.progress.exercises
                for attempt in exercise.attempts
                for review in attempt.reviews
            ):
                raise ValueError("rationale history exists while retention is disabled")
        if len(self.style_bible_assets) != len(set(self.style_bible_assets)):
            raise ValueError("style-bible asset paths must be unique")
        for asset in self.style_bible_assets:
            path = PurePosixPath(asset)
            if not asset.strip() or path.is_absolute() or ".." in path.parts or "\\" in asset:
                raise ValueError("style-bible assets must use safe relative POSIX paths")
        if len(self.correspondence_set_assets) != len(set(self.correspondence_set_assets)):
            raise ValueError("correspondence-set asset paths must be unique")
        for asset in self.correspondence_set_assets:
            path = PurePosixPath(asset)
            if not asset.strip() or path.is_absolute() or ".." in path.parts or "\\" in asset:
                raise ValueError("correspondence-set assets must use safe relative POSIX paths")
        if len(self.editor_document_assets) != len(set(self.editor_document_assets)):
            raise ValueError("editor-document asset paths must be unique")
        for asset in self.editor_document_assets:
            path = PurePosixPath(asset)
            if not asset.strip() or path.is_absolute() or ".." in path.parts or "\\" in asset:
                raise ValueError("editor-document assets must use safe relative POSIX paths")
        for exercise in self.progress.exercises:
            for attempt in exercise.attempts:
                review_ids = [review.id for review in attempt.reviews]
                if len(review_ids) != len(set(review_ids)):
                    raise ValueError("review identifiers must be unique within an attempt")
                for review in attempt.reviews:
                    entries = review.artist_feedback_history + (
                        [review.artist_feedback] if review.artist_feedback is not None else []
                    )
                    if any(
                        item.note is not None
                        and len(item.note) > self.feedback_policy.note_character_limit
                        for item in entries
                    ):
                        raise ValueError("stored advice feedback exceeds the configured note limit")
                    if (
                        not self.feedback_policy.retain_revision_history
                        and review.artist_feedback_history
                    ):
                        raise ValueError(
                            "feedback history exists while revision retention is disabled"
                        )
        if not self.study_consent.opted_in and self.study_sessions:
            raise ValueError("study sessions exist while study consent is not opted in")
        session_ids = [session.id for session in self.study_sessions]
        if len(session_ids) != len(set(session_ids)):
            raise ValueError("study-session identifiers must be unique")
        known_attempt_ids = {
            attempt.id for exercise in self.progress.exercises for attempt in exercise.attempts
        }
        for session in self.study_sessions:
            if session.baseline_attempt_id not in known_attempt_ids:
                raise ValueError("study-session baseline attempt id is unknown")
            if (
                session.redraw_attempt_id is not None
                and session.redraw_attempt_id not in known_attempt_ids
            ):
                raise ValueError("study-session redraw attempt id is unknown")
        page_ids = [page.id for page in self.chapter_pages]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("chapter-page identifiers must be unique")
        page_assets = [page.document_asset for page in self.chapter_pages]
        if len(page_assets) != len(set(page_assets)):
            raise ValueError("chapter-page document assets must be unique")
        page_panel_ids = [page.panel_id for page in self.chapter_pages]
        if len(page_panel_ids) != len(set(page_panel_ids)):
            raise ValueError("chapter-page panel ids must be unique")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Project:
        """Validate and deserialize a project manifest."""
        payload = migrate_project_payload(payload)
        version = payload.get("schema_version")
        if version != CURRENT_SCHEMA_VERSION:
            raise ValueError(f"unsupported project schema version: {version}")
        consent = Consent(**payload.get("consent", {}))
        autosave = AutosavePolicy(**payload.get("autosave", {}))
        feedback_policy = FeedbackPolicy(**payload.get("feedback_policy", {}))
        identity_card_policy = IdentityCardPolicy(**payload.get("identity_card_policy", {}))
        capstone_policy = CapstonePolicy(**payload.get("capstone_policy", {}))
        identity_card = _identity_card_from_payload(payload.get("identity_card"))
        identity_card_history = [
            _identity_card_from_payload(item) for item in payload.get("identity_card_history", [])
        ]
        exercises = []
        for raw_exercise in payload.get("progress", {}).get("exercises", []):
            attempts = []
            for raw_attempt in raw_exercise.get("attempts", []):
                feedback = [Feedback(**item) for item in raw_attempt.get("feedback", [])]
                reviews = [
                    ReviewRecord(
                        **(
                            item
                            | {
                                "suggestion_decision": SuggestionDecision(
                                    item.get("suggestion_decision", "pending")
                                ),
                                "artist_feedback": (
                                    AdviceFeedback(
                                        AdviceRating(item["artist_feedback"]["rating"]),
                                        item["artist_feedback"].get("note"),
                                        item["artist_feedback"].get("revision", 1),
                                    )
                                    if item.get("artist_feedback") is not None
                                    else None
                                ),
                                "artist_feedback_history": [
                                    AdviceFeedback(
                                        AdviceRating(history["rating"]),
                                        history.get("note"),
                                        history.get("revision", 1),
                                    )
                                    for history in item.get("artist_feedback_history", [])
                                ],
                                "suggestion_decision_rationale_history": [
                                    RationaleRevision(**history)
                                    for history in item.get(
                                        "suggestion_decision_rationale_history", []
                                    )
                                ],
                            }
                        )
                    )
                    for item in raw_attempt.get("reviews", [])
                ]
                attempts.append(
                    Attempt(**(raw_attempt | {"feedback": feedback, "reviews": reviews}))
                )
            exercises.append(ExerciseProgress(raw_exercise["exercise_id"], attempts))
        project = cls(
            title=payload["title"],
            id=payload["id"],
            schema_version=version,
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            document_asset=payload.get("document_asset"),
            consent=consent,
            autosave=autosave,
            feedback_policy=feedback_policy,
            identity_card_policy=identity_card_policy,
            capstone_policy=capstone_policy,
            identity_card=identity_card,
            identity_card_history=[item for item in identity_card_history if item is not None],
            style_bible_assets=list(payload.get("style_bible_assets", [])),
            correspondence_set_assets=list(payload.get("correspondence_set_assets", [])),
            editor_document_assets=list(payload.get("editor_document_assets", [])),
            study_consent=StudyConsent(**payload.get("study_consent", {})),
            study_sessions=[
                StudySession(
                    **(
                        item
                        | {
                            "explanation_rating": (
                                AdviceRating(item["explanation_rating"])
                                if item.get("explanation_rating") is not None
                                else None
                            )
                        }
                    )
                )
                for item in payload.get("study_sessions", [])
            ],
            chapter_pages=[
                ChapterPage(**(item | {"status": PageStatus(item["status"])}))
                for item in payload.get("chapter_pages", [])
            ],
            signal_weights=SignalWeights(**payload.get("signal_weights", {})),
            progress=ProjectProgress(exercises),
        )
        project.validate()
        return project


def _identity_card_from_payload(payload):
    if payload is None:
        return None
    return IdentityCard(
        name=payload["name"],
        anchors=[IdentityAnchor(**item) for item in payload["anchors"]],
        revision=payload.get("revision", 1),
    )


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
        if payload.get("schema_version") in (1, 2, 3):
            payload = payload | {"schema_version": CURRENT_SCHEMA_VERSION}
        profile = cls(**payload)
        profile.to_dict()
        return profile
