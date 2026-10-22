"""Convert service coordinator implementing ConvertServiceProtocol (Issue #881, Wave 0e W0-17)."""

from __future__ import annotations

from middleware.src.services.base import Handler
from middleware.src.services.convert.commands import (
    BatchConvertCommand,
    BatchConvertResult,
    ConvertSingleCommand,
    ConvertSingleResult,
)
from middleware.src.services.convert.handlers import BatchConvertHandler, ConvertSingleHandler
from middleware.src.services.convert.protocols import ConvertServiceProtocol


class ConvertService(ConvertServiceProtocol):
    """Canonical domain service for image conversion."""

    def __init__(
        self,
        single_handler: Handler[ConvertSingleCommand, ConvertSingleResult] | None = None,
        batch_handler: Handler[BatchConvertCommand, BatchConvertResult] | None = None,
    ) -> None:
        self._single_handler = single_handler or ConvertSingleHandler()
        self._batch_handler = batch_handler or BatchConvertHandler(self._single_handler)

    def convert_single(self, command: ConvertSingleCommand) -> ConvertSingleResult:
        """Convert a single image."""
        return self._single_handler.handle(command)

    def convert_batch(self, command: BatchConvertCommand) -> BatchConvertResult:
        """Convert a batch of images from a source directory."""
        return self._batch_handler.handle(command)
