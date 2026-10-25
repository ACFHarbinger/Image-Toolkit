"""Scan & Tag service coordinator implementing ScanServiceProtocol (L-04 / #898, Issue #881)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.base import Handler
from middleware.src.services.scan.commands import (
    SaveMetadataCommand,
    SaveMetadataResult,
    ScanDirectoryCommand,
    ScanDirectoryResult,
    SuggestTagsCommand,
    SuggestTagsResult,
)
from middleware.src.services.scan.handlers import (
    SaveMetadataHandler,
    ScanDirectoryHandler,
    SuggestTagsHandler,
)
from middleware.src.services.scan.protocols import ScanServiceProtocol


class ScanService(ScanServiceProtocol):
    """Canonical domain service for library directory scanning and metadata tagging."""

    def __init__(
        self,
        db_session: Any | None = None,
        scan_handler: Handler[ScanDirectoryCommand, ScanDirectoryResult] | None = None,
        save_handler: Handler[SaveMetadataCommand, SaveMetadataResult] | None = None,
        suggest_handler: Handler[SuggestTagsCommand, SuggestTagsResult] | None = None,
    ) -> None:
        self._db_session = db_session
        self._scan_handler = scan_handler or ScanDirectoryHandler(db_session=db_session)
        self._save_handler = save_handler or SaveMetadataHandler(db_session=db_session)
        self._suggest_handler = suggest_handler or SuggestTagsHandler()

    def scan_directory(self, command: ScanDirectoryCommand) -> ScanDirectoryResult:
        """Scan a filesystem directory for image assets and metadata."""
        return self._scan_handler.handle(command)

    def save_metadata(self, command: SaveMetadataCommand) -> SaveMetadataResult:
        """Save metadata, groups, subgroups, and tags for scanned image assets."""
        return self._save_handler.handle(command)

    def suggest_tags(self, command: SuggestTagsCommand) -> SuggestTagsResult:
        """Generate heuristic tag suggestions from image paths and folder structure."""
        return self._suggest_handler.handle(command)
