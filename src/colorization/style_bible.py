"""Versioned, portable character style-bible and palette contract."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import Any

STYLE_BIBLE_SCHEMA_VERSION = 1
_IDENTIFIER = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_COLOR = re.compile(r"^#[0-9A-F]{6}$")


@dataclass(frozen=True, slots=True)
class MaterialPalette:
    local: str
    light: str
    shadow: str
    accent: str | None = None

    def __post_init__(self) -> None:
        values = [self.local, self.light, self.shadow]
        if self.accent is not None:
            values.append(self.accent)
        if any(not _COLOR.fullmatch(value) for value in values):
            raise ValueError("palette colors must use uppercase #RRGGBB sRGB notation")


@dataclass(frozen=True, slots=True)
class StyleMaterial:
    id: str
    label: str
    palette: MaterialPalette
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier(self.id, "material")
        if not self.label.strip():
            raise ValueError("material label must not be empty")
        normalized = [alias.strip().casefold() for alias in self.aliases]
        if any(not alias for alias in normalized) or len(normalized) != len(set(normalized)):
            raise ValueError("material aliases must be non-empty and unique")


@dataclass(frozen=True, slots=True)
class ReferenceView:
    id: str
    label: str
    asset_path: str
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier(self.id, "reference view")
        if not self.label.strip():
            raise ValueError("reference-view label must not be empty")
        path = PurePosixPath(self.asset_path)
        if (
            not self.asset_path.strip()
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in self.asset_path
        ):
            raise ValueError("reference asset must be a safe project-relative POSIX path")
        if self.notes is not None and not self.notes.strip():
            raise ValueError("reference notes must be absent or non-empty")


@dataclass(slots=True)
class CharacterStyleBible:
    id: str
    character_name: str
    style_name: str
    materials: list[StyleMaterial]
    reference_views: list[ReferenceView] = field(default_factory=list)
    recovery_revisions: int = 10
    schema_version: int = STYLE_BIBLE_SCHEMA_VERSION

    def validate(self) -> None:
        if self.schema_version != STYLE_BIBLE_SCHEMA_VERSION:
            raise ValueError(f"unsupported style-bible schema version: {self.schema_version}")
        _validate_identifier(self.id, "style bible")
        if not self.character_name.strip() or not self.style_name.strip():
            raise ValueError("character and style names must not be empty")
        if not self.materials:
            raise ValueError("style bible must define at least one material")
        _require_unique("material", [item.id for item in self.materials])
        _require_unique("reference-view", [item.id for item in self.reference_views])
        aliases: dict[str, str] = {}
        for material in self.materials:
            for name in (material.id, material.label, *material.aliases):
                key = name.strip().casefold()
                if key in aliases and aliases[key] != material.id:
                    raise ValueError("material names and aliases must resolve unambiguously")
                aliases[key] = material.id
        if not isinstance(self.recovery_revisions, int) or not 1 <= self.recovery_revisions <= 100:
            raise ValueError("style-bible recovery revisions must be between 1 and 100")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CharacterStyleBible:
        allowed = {
            "id",
            "character_name",
            "style_name",
            "materials",
            "reference_views",
            "recovery_revisions",
            "schema_version",
        }
        if set(payload) - allowed:
            raise ValueError("style-bible payload contains unknown fields")
        try:
            bible = cls(
                id=payload["id"],
                character_name=payload["character_name"],
                style_name=payload["style_name"],
                materials=[
                    StyleMaterial(
                        id=item["id"],
                        label=item["label"],
                        aliases=tuple(item.get("aliases", ())),
                        palette=MaterialPalette(**item["palette"]),
                    )
                    for item in payload["materials"]
                ],
                reference_views=[
                    ReferenceView(**item) for item in payload.get("reference_views", [])
                ],
                recovery_revisions=payload.get("recovery_revisions", 10),
                schema_version=payload.get("schema_version", 0),
            )
        except (KeyError, TypeError) as error:
            raise ValueError("style-bible payload is incomplete or malformed") from error
        bible.validate()
        return bible


def save_style_bible(path: str | Path, bible: CharacterStyleBible) -> Path:
    """Atomically save a bible and rotate bounded JSON recovery revisions."""
    destination = Path(path)
    bible.validate()
    if destination.exists():
        _rotate_recovery(destination, bible.recovery_revisions)
    _atomic_write(destination, bible.to_dict())
    return destination


def load_style_bible(path: str | Path) -> CharacterStyleBible:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("style-bible root must be an object")
    return CharacterStyleBible.from_dict(payload)


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
    previous = load_style_bible(path)
    _atomic_write(recovery / f"{path.stem}.1.json", previous.to_dict())


def _validate_identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} id must use lowercase kebab-case")


def _require_unique(label: str, values: list[str]) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} identifiers must be unique")
