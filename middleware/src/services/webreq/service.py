"""WebRequests service coordinator implementing WebRequestsServiceProtocol (B-02 / #907)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.base import Handler
from middleware.src.services.webreq.commands import (
    ExecuteCommand,
    ExecuteResult,
    SequenceCommand,
    SequenceResult,
)
from middleware.src.services.webreq.handlers import ExecuteHandler, SequenceHandler
from middleware.src.services.webreq.protocols import WebRequestsServiceProtocol


class WebRequestsService(WebRequestsServiceProtocol):
    """Canonical domain service for web requests sequence and isolated HTTP execution."""

    def __init__(
        self,
        execute_handler: Handler[ExecuteCommand, ExecuteResult] | None = None,
        sequence_handler: Handler[SequenceCommand, SequenceResult] | None = None,
        logic_cls: Any | None = None,
    ) -> None:
        self._execute_handler = execute_handler or ExecuteHandler()
        self._sequence_handler = sequence_handler or SequenceHandler(logic_cls=logic_cls)

    def execute(self, command: ExecuteCommand) -> ExecuteResult:
        """Execute a single HTTP request."""
        return self._execute_handler.handle(command)

    def sequence(self, command: SequenceCommand) -> SequenceResult:
        """Execute a sequential pipeline of HTTP requests with response actions."""
        return self._sequence_handler.handle(command)
