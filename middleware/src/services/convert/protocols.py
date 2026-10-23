"""Protocols for the Convert service (Issue #881, Wave 0e W0-17).

Runtime-checkable protocol defining the Convert service boundary.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from middleware.src.services.base import ServiceProtocol
from middleware.src.services.convert.commands import (
    BatchConvertCommand,
    BatchConvertResult,
    ConvertSingleCommand,
    ConvertSingleResult,
)


@runtime_checkable
class ConvertServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for image conversion service implementations."""

    def convert_single(self, command: ConvertSingleCommand) -> ConvertSingleResult:
        """Convert a single image file."""
        ...

    def convert_batch(self, command: BatchConvertCommand) -> BatchConvertResult:
        """Convert a batch of images from a source directory."""
        ...
