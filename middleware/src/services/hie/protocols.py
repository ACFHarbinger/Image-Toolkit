"""Protocols for the Hybrid Image Editor (HIE) service.

Runtime-checkable protocol defining the boundary for hybrid editing operations
(W0-03 Phase C, #867).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from middleware.src.services.base import ServiceProtocol
from middleware.src.services.hie.commands import (
    HieEditCommand,
    HieEditResult,
    HieExportDocumentCommand,
    HieExportDocumentResult,
    HieListCapabilitiesCommand,
    HieListCapabilitiesResult,
    HieOpenDocumentCommand,
    HieOpenDocumentResult,
)


@runtime_checkable
class HieServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for hybrid document editing and pipeline execution."""

    def open_document(self, command: HieOpenDocumentCommand) -> HieOpenDocumentResult:
        """Open or initialize an image document session."""
        ...

    def execute_edit(self, command: HieEditCommand) -> HieEditResult:
        """Apply an editing operation to an active document session."""
        ...

    def export_document(self, command: HieExportDocumentCommand) -> HieExportDocumentResult:
        """Export a document session to destination media file."""
        ...

    def list_capabilities(
        self, command: HieListCapabilitiesCommand | None = None
    ) -> HieListCapabilitiesResult:
        """Query supported operations and available neural model adapters."""
        ...
