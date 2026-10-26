"""Protocol definitions for the WebRequests service (B-02 / #907)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from middleware.src.services.webreq.commands import (
    ExecuteCommand,
    ExecuteResult,
    SequenceCommand,
    SequenceResult,
)


@runtime_checkable
class WebRequestsServiceProtocol(Protocol):
    """Protocol declaring capabilities of the web requests service."""

    def execute(self, command: ExecuteCommand) -> ExecuteResult:
        """Execute a single HTTP request."""
        ...

    def sequence(self, command: SequenceCommand) -> SequenceResult:
        """Execute a sequential pipeline of HTTP requests with response actions."""
        ...
