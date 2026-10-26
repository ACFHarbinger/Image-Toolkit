"""Versioned, portable region-to-material correspondence contract.

A correspondence set records which target-drawing region an artist assigned
to which canonical style-bible material/role. It stores identifiers and
provenance only, never pixels, embeddings, or inferred identity. Propagation
only ever applies to regions the artist explicitly selected; it never
discovers or guesses regions on its own.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

CORRESPONDENCE_SCHEMA_VERSION = 1
CORRESPONDENCE_ROLES = frozenset({"local", "light", "shadow", "accent"})
_IDENTIFIER = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class RegionCorrespondence:
    id: str
    region_id: str
    material_id: str
    role: str = "local"
    panel_id: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier(self.id, "correspondence")
        _validate_identifier(self.region_id, "region")
        _validate_identifier(self.material_id, "material")
        if self.role not in CORRESPONDENCE_ROLES:
            raise ValueError("correspondence role is not supported")
        if self.panel_id is not None:
            _validate_identifier(self.panel_id, "panel")
        if self.notes is not None and not self.notes.strip():
            raise ValueError("correspondence notes must be absent or non-empty")

    @property
    def _assignment_key(self) -> tuple[str, str | None]:
        return (self.region_id, self.panel_id)


@dataclass(slots=True)
class CorrespondenceSet:
    id: str
    style_bible_id: str
    correspondences: list[RegionCorrespondence] = field(default_factory=list)
    recovery_revisions: int = 10
    schema_version: int = CORRESPONDENCE_SCHEMA_VERSION

    def validate(self) -> None:
        if self.schema_version != CORRESPONDENCE_SCHEMA_VERSION:
            raise ValueError(f"unsupported correspondence schema version: {self.schema_version}")
        _validate_identifier(self.id, "correspondence set")
        _validate_identifier(self.style_bible_id, "style bible")
        _require_unique("correspondence", [item.id for item in self.correspondences])
        assignments: dict[tuple[str, str | None], str] = {}
        for item in self.correspondences:
            key = item._assignment_key
            if key in assignments and assignments[key] != item.material_id:
                raise ValueError(
                    "region is assigned to competing materials; correct the ambiguity "
                    "explicitly instead of guessing"
                )
            assignments[key] = item.material_id
        if not isinstance(self.recovery_revisions, int) or not 1 <= self.recovery_revisions <= 100:
            raise ValueError("correspondence recovery revisions must be between 1 and 100")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CorrespondenceSet:
        payload = migrate_correspondence_payload(payload)
        allowed = {
            "id",
            "style_bible_id",
            "correspondences",
            "recovery_revisions",
            "schema_version",
        }
        if set(payload) - allowed:
            raise ValueError("correspondence-set payload contains unknown fields")
        try:
            correspondence_set = cls(
                id=payload["id"],
                style_bible_id=payload["style_bible_id"],
                correspondences=[
                    RegionCorrespondence(**item) for item in payload.get("correspondences", [])
                ],
                recovery_revisions=payload.get("recovery_revisions", 10),
                schema_version=payload["schema_version"],
            )
        except (KeyError, TypeError) as error:
            raise ValueError("correspondence-set payload is incomplete or malformed") from error
        correspondence_set.validate()
        return correspondence_set

    def propagate(
        self,
        source_id: str,
        target_region_ids: list[str],
        new_id_factory: Any,
    ) -> CorrespondenceSet:
        """Return a copy with the source assignment applied to explicit targets.

        Targets are never discovered automatically. Any target already
        assigned to a different material is reported as ambiguous rather than
        silently overwritten or skipped.
        """
        source = next((item for item in self.correspondences if item.id == source_id), None)
        if source is None:
            raise ValueError("propagation source correspondence does not exist")
        if not target_region_ids:
            raise ValueError("propagation requires at least one explicit target region")
        existing_by_region: dict[tuple[str, str | None], RegionCorrespondence] = {
            item._assignment_key: item for item in self.correspondences
        }
        added: list[RegionCorrespondence] = []
        for region_id in target_region_ids:
            key = (region_id, source.panel_id)
            conflict = existing_by_region.get(key)
            if conflict is not None and conflict.material_id != source.material_id:
                raise ValueError(
                    f"region '{region_id}' already has a competing assignment; "
                    "resolve the conflict explicitly before propagating"
                )
            if conflict is not None:
                continue
            added.append(
                RegionCorrespondence(
                    id=new_id_factory(),
                    region_id=region_id,
                    material_id=source.material_id,
                    role=source.role,
                    panel_id=source.panel_id,
                )
            )
        propagated = CorrespondenceSet(
            id=self.id,
            style_bible_id=self.style_bible_id,
            correspondences=[*self.correspondences, *added],
            recovery_revisions=self.recovery_revisions,
            schema_version=self.schema_version,
        )
        propagated.validate()
        return propagated


def migrate_correspondence_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a schema-current copy, rejecting anything not already current."""
    if not isinstance(payload, dict):
        raise ValueError("correspondence-set payload must be an object")
    version = payload.get("schema_version", 0)
    if version != CORRESPONDENCE_SCHEMA_VERSION:
        raise ValueError(f"unsupported correspondence schema version: {version}")
    return dict(payload)


def save_correspondence_set(path: str | Path, correspondence_set: CorrespondenceSet) -> Path:
    """Atomically save a correspondence set and rotate bounded JSON recovery revisions."""
    destination = Path(path)
    correspondence_set.validate()
    if destination.exists():
        _rotate_recovery(destination, correspondence_set.recovery_revisions)
    _atomic_write(destination, correspondence_set.to_dict())
    return destination


def load_correspondence_set(path: str | Path) -> CorrespondenceSet:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("correspondence-set root must be an object")
    return CorrespondenceSet.from_dict(payload)


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _rotate_recovery(path: Path, revisions: int) -> None:
    recovery = path.parent / ".recovery"
    recovery.mkdir(exist_ok=True)
    for number in range(revisions, 1, -1):
        older = recovery / f"{path.stem}.{number - 1}.json"
        newer = recovery / f"{path.stem}.{number}.json"
        if older.exists():
            os.replace(older, newer)
    previous = load_correspondence_set(path)
    _atomic_write(recovery / f"{path.stem}.1.json", previous.to_dict())


def _validate_identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} id must use lowercase kebab-case")


def _require_unique(label: str, values: list[str]) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} identifiers must be unique")
