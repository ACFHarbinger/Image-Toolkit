"""Domain service layer for Image-Toolkit (Issue #881, Wave 0e W0-17).

Provides pure Python domain services implementing the Command/Handler pattern
with runtime-checkable Protocol interfaces and immutable frozen dataclasses.
Decoupled from UI (PySide6, React), transport/IPC (JSON-RPC), and webview.
"""

from __future__ import annotations

from middleware.src.services.base import (
    Command,
    CommandValidationError,
    EntityNotFoundError,
    Handler,
    Result,
    ServiceError,
    ServiceExecutionError,
    ServiceProtocol,
)

__all__ = [
    "Command",
    "CommandValidationError",
    "EntityNotFoundError",
    "Handler",
    "Result",
    "ServiceError",
    "ServiceExecutionError",
    "ServiceProtocol",
]
