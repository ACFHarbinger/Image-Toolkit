"""Protocol definitions for the Scan service (L-04 / #898, Issue #881)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from middleware.src.services.scan.commands import (
    SaveMetadataCommand,
    SaveMetadataResult,
    ScanDirectoryCommand,
    ScanDirectoryResult,
    SuggestTagsCommand,
    SuggestTagsResult,
)


@runtime_checkable
class ScanServiceProtocol(Protocol):
    """Protocol declaring capabilities of the directory scan & metadata service."""

    def scan_directory(self, command: ScanDirectoryCommand) -> ScanDirectoryResult:
        """Scan a filesystem directory for image assets and metadata."""
        ...

    def save_metadata(self, command: SaveMetadataCommand) -> SaveMetadataResult:
        """Save metadata, groups, subgroups, and tags for scanned image assets."""
        ...

    def suggest_tags(self, command: SuggestTagsCommand) -> SuggestTagsResult:
        """Generate heuristic tag suggestions from image paths and folder structure."""
        ...
