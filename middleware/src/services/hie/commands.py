"""Commands and results for the Hybrid Image Editor (HIE) service.

Defines immutable frozen dataclasses for document opening, editing,
exporting, and capabilities querying (W0-03 Phase C, #867).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from middleware.src.services.base import Command, Result


@dataclass(frozen=True)
class HieOpenDocumentCommand(Command):
    """Command to load media into a HIE document session."""

    source: str
    document_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HieOpenDocumentResult(Result):
    """Result of opening a HIE document."""

    success: bool
    document_id: str
    frame_count: int = 0
    width: int = 0
    height: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class HieEditCommand(Command):
    """Command to apply an editing operation to a HIE document."""

    document_id: str
    operation: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HieEditResult(Result):
    """Result of an editing operation on a HIE document."""

    success: bool
    document_id: str
    output_document_id: str | None = None
    modified_layers: tuple[str, ...] = ()
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class HieExportDocumentCommand(Command):
    """Command to render and export a HIE document to an image/video file."""

    document_id: str
    output_path: str
    format: str = "png"
    quality: int = 95


@dataclass(frozen=True)
class HieExportDocumentResult(Result):
    """Result of exporting a HIE document."""

    success: bool
    output_path: str
    size_bytes: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class HieListCapabilitiesCommand(Command):
    """Command to inspect available editing operations and ML models."""


@dataclass(frozen=True)
class HieListCapabilitiesResult(Result):
    """Result of querying HIE editor capabilities."""

    capabilities: tuple[str, ...] = ()
    models_available: tuple[str, ...] = ()
    error: str | None = None
