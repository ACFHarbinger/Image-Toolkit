"""Service-layer architectural base primitives (Issue #881, Wave 0e W0-17).

Defines the Command/Handler pattern, runtime-checkable service protocols,
and domain error primitives. Pure Python, decoupled from UI/GUI frameworks
and bridge/transport mechanisms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar, runtime_checkable

# Generic type variables for Command and Result
CommandT = TypeVar("CommandT")
ResultT = TypeVar("ResultT")


class ServiceError(Exception):
    """Base exception for all service layer operations."""

    def __init__(self, message: str, code: str = "service_error", details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class CommandValidationError(ServiceError):
    """Raised when command parameters fail business or schema validation."""

    def __init__(self, message: str, field: str | None = None) -> None:
        details = {"field": field} if field else {}
        super().__init__(message, code="validation_error", details=details)


class EntityNotFoundError(ServiceError):
    """Raised when an entity or resource required by the command does not exist."""

    def __init__(self, message: str, entity_type: str = "entity", entity_id: str | None = None) -> None:
        details = {"entity_type": entity_type}
        if entity_id:
            details["entity_id"] = entity_id
        super().__init__(message, code="not_found", details=details)


class ServiceExecutionError(ServiceError):
    """Raised when underlying execution (I/O, image processing, engine) fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        details = {"cause": str(original_error)} if original_error else {}
        super().__init__(message, code="execution_error", details=details)


@dataclass(frozen=True)
class Command:
    """Base marker class for immutable service commands."""


@dataclass(frozen=True)
class Result:
    """Base marker class for immutable service command results."""


@runtime_checkable
class Handler(Protocol[CommandT, ResultT]):
    """Generic protocol for command handlers.

    A handler encapsulates the business logic for executing a single
    command type and producing its corresponding result.
    """

    def handle(self, command: CommandT) -> ResultT:
        """Execute the command and return the resulting value."""
        ...


@runtime_checkable
class ServiceProtocol(Protocol):
    """Base marker protocol for domain services."""

    ...
