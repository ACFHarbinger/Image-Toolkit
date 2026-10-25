"""Commands and results for the Scan & Tag service (L-04 / #898, Issue #881)."""

from __future__ import annotations

from dataclasses import dataclass

from middleware.src.services.base import Command, Result


@dataclass(frozen=True)
class ScannedImageRecord:
    """Record describing an image found on disk during a directory scan."""

    path: str
    filename: str
    extension: str
    size_bytes: int
    in_database: bool
    width: int | None = None
    height: int | None = None
    tags: tuple[str, ...] = ()
    group_name: str | None = None
    subgroup_name: str | None = None


@dataclass(frozen=True)
class ScanDirectoryCommand(Command):
    """Command to scan a directory for image files and resolve basic metadata."""

    directory: str
    recursive: bool = False
    formats: tuple[str, ...] = ("webp", "png", "jpg", "jpeg", "gif")
    max_results: int = 500


@dataclass(frozen=True)
class ScanDirectoryResult(Result):
    """Result of a directory scan operation."""

    directory: str
    total_found: int
    images: tuple[ScannedImageRecord, ...]
    database_available: bool = False


@dataclass(frozen=True)
class MetadataItemCommand:
    """Single image metadata assignment."""

    path: str
    tags: tuple[str, ...] = ()
    group_name: str | None = None
    subgroup_name: str | None = None


@dataclass(frozen=True)
class SaveMetadataCommand(Command):
    """Command to persist tags and group assignments for scanned images."""

    items: tuple[MetadataItemCommand, ...]


@dataclass(frozen=True)
class SaveMetadataResult(Result):
    """Result of a metadata persistence operation."""

    saved_count: int
    success: bool
    database_available: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class SuggestTagsCommand(Command):
    """Command to generate tag suggestions based on folder hierarchy and filenames."""

    paths: tuple[str, ...]


@dataclass(frozen=True)
class SuggestTagsResult(Result):
    """Result containing tag suggestions mapped by image path."""

    suggestions: dict[str, tuple[str, ...]]
