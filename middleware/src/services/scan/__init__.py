"""Scan & Tag service domain package (L-04 / #898, Issue #881)."""

from __future__ import annotations

from middleware.src.services.scan.commands import (
    MetadataItemCommand,
    SaveMetadataCommand,
    SaveMetadataResult,
    ScanDirectoryCommand,
    ScanDirectoryResult,
    ScannedImageRecord,
    SuggestTagsCommand,
    SuggestTagsResult,
)
from middleware.src.services.scan.protocols import ScanServiceProtocol
from middleware.src.services.scan.service import ScanService

__all__ = [
    "MetadataItemCommand",
    "SaveMetadataCommand",
    "SaveMetadataResult",
    "ScanDirectoryCommand",
    "ScanDirectoryResult",
    "ScanService",
    "ScanServiceProtocol",
    "ScannedImageRecord",
    "SuggestTagsCommand",
    "SuggestTagsResult",
]
