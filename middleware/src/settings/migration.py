"""Backed-up legacy settings migration (W0-16 / #880).

Imports the Qt shell's legacy QSettings file (INI format, e.g.
``~/.config/ImageToolkit/ImageToolkit.conf`` on Linux) into the shared
settings service. Two guarantees:

1. **Backup first.** The legacy file is copied to
   ``<name>.<YYYYmmdd-HHMMSS>.bak`` next to it before anything is
   written, and the original is never modified — a failed migration can
   always be retried from the untouched source.
2. **Conflicts are detected, never silently resolved.** A key present in
   both stores with different values is reported; the
   :class:`~middleware.src.settings.conflicts.ConflictPolicy` decides
   (abort by default).

QSettings INI payloads are carried verbatim for keys the shared catalog
types as ``bytes`` (``mainwindow/geometry``'s ``@ByteArray(...)``): the
service keeps the raw payload, and the Qt consumer re-interprets it when
the shells delegate to this service.
"""

from __future__ import annotations

import configparser
import contextlib
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .conflicts import ConflictPolicy, MigrationConflictError, SettingsConflict
from .keys import definition_for
from .service import SettingsService

_GENERAL = "General"
_MARKER_PREFIX = "@"


class MigrationError(Exception):
    """The legacy source could not be read or backed up."""


def _decode_value(raw: str) -> Any:
    """Decode one QSettings INI value; marker payloads stay verbatim."""
    stripped = raw.strip()
    if stripped.startswith(_MARKER_PREFIX):
        # @ByteArray(...) / @Invalid() — re-interpreted by the Qt consumer
        return raw
    if stripped in ("true", "false"):
        return stripped == "true"
    with contextlib.suppress(ValueError):
        return int(stripped)
    with contextlib.suppress(ValueError):
        return float(stripped)
    return raw


@dataclass(frozen=True)
class MigrationReport:
    """What a migration did, for the settings UI to show."""

    backup_path: Path
    migrated_keys: list[str]
    skipped_keys: list[str]
    conflicts: list[SettingsConflict]


def read_legacy_qsettings(path: str | Path) -> dict[str, Any]:
    """Parse a QSettings NativeFormat INI file into a flat key map.

    QSettings writes slash-separated keys as INI sections; the
    ``[General]`` section holds top-level keys. Raw payloads keep their
    ``@ByteArray(...)`` / ``@Invalid()`` markers so nothing is lost.
    """
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str  # type: ignore[assignment]
    read = parser.read(path, encoding="utf-8")
    if not read:
        raise MigrationError(f"cannot read legacy settings file: {path}")

    entries: dict[str, Any] = {}
    for section in parser.sections():
        for name, raw in parser.items(section):
            value = _decode_value(raw)
            entries[f"{section}/{name}" if section != _GENERAL else name] = value
    return entries


def backup_legacy_file(path: str | Path) -> Path:
    """Copy the legacy file to a timestamped backup beside it (first)."""
    source = Path(path)
    if not source.is_file():
        raise MigrationError(f"legacy settings file not found: {source}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = source.with_name(f"{source.name}.{stamp}.bak")
    if backup.exists():
        raise MigrationError(f"backup already exists: {backup}")
    shutil.copy2(source, backup)
    return backup


def migrate_legacy(
    service: SettingsService,
    legacy_path: str | Path,
    policy: ConflictPolicy = ConflictPolicy.ABORT,
) -> MigrationReport:
    """Import legacy settings into the service, backup first.

    The legacy file itself is never written to. Typed values are cast by
    the catalog; keys already present with a different value are
    conflicts resolved per ``policy`` (``ABORT`` writes nothing and
    raises; ``PREFER_NEW`` skips the legacy value).
    """
    backup = backup_legacy_file(legacy_path)
    entries: dict[str, Any] = {}
    for key, value in read_legacy_qsettings(legacy_path).items():
        definition = definition_for(key)
        if definition is not None and definition.value_type is not bytes:
            value = definition.cast(value)
        entries[key] = value

    conflicts = [
        SettingsConflict(key=key, legacy_value=value, new_value=service.get(key))
        for key, value in entries.items()
        if service.contains(key) and service.get(key) != value
    ]
    if policy is ConflictPolicy.ABORT and conflicts:
        raise MigrationConflictError(conflicts)

    conflict_keys = {conflict.key for conflict in conflicts}
    migrated: list[str] = []
    skipped: list[str] = []
    for key, value in entries.items():
        if key in conflict_keys and policy is ConflictPolicy.PREFER_NEW:
            skipped.append(key)
            continue
        service.set(key, value)
        migrated.append(key)

    return MigrationReport(
        backup_path=backup,
        migrated_keys=migrated,
        skipped_keys=skipped,
        conflicts=conflicts,
    )


__all__ = [
    "MigrationError",
    "MigrationReport",
    "backup_legacy_file",
    "migrate_legacy",
    "read_legacy_qsettings",
]
