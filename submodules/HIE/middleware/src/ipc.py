"""Versioned JSON envelopes shared by the PySide6/Tauri host boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


IPC_VERSION = 1
SUPPORTED_METHODS = frozenset(
    {
        "open_media",
        "export_document",
        "notify",
        "list_capabilities",
        "preview_policy",
        "accept_proposal",
        "submit_restoration",
    }
)


class IpcContractError(ValueError):
    """Raised when a frontend/native-host envelope is malformed."""


@dataclass(frozen=True)
class IpcRequest:
    """A versioned command sent from a frontend to its host."""

    request_id: str
    method: str
    payload: dict[str, Any] = field(default_factory=dict)
    version: int = IPC_VERSION

    def __post_init__(self) -> None:
        _validate_common(self.request_id, self.version)
        if self.method not in SUPPORTED_METHODS:
            raise IpcContractError(f"unsupported IPC method: {self.method!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "request_id": self.request_id,
            "method": self.method,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "IpcRequest":
        if not isinstance(value, Mapping):
            raise IpcContractError("IPC request must be an object")
        try:
            return cls(
                request_id=value["request_id"],
                method=value["method"],
                payload=dict(value.get("payload", {})),
                version=value.get("version", IPC_VERSION),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise IpcContractError("invalid IPC request fields") from exc


@dataclass(frozen=True)
class IpcResponse:
    """A versioned host result suitable for Tauri invoke or HTTP transport."""

    request_id: str
    status: str
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    version: int = IPC_VERSION

    def __post_init__(self) -> None:
        _validate_common(self.request_id, self.version)
        if self.status not in {"ok", "error"}:
            raise IpcContractError("IPC response status must be 'ok' or 'error'")
        if self.status == "error" and not self.error:
            raise IpcContractError("error responses require an error message")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "request_id": self.request_id,
            "status": self.status,
            "payload": self.payload,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "IpcResponse":
        if not isinstance(value, Mapping):
            raise IpcContractError("IPC response must be an object")
        try:
            return cls(
                request_id=value["request_id"],
                status=value["status"],
                payload=dict(value.get("payload", {})),
                error=value.get("error"),
                version=value.get("version", IPC_VERSION),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise IpcContractError("invalid IPC response fields") from exc


def _validate_common(request_id: str, version: int) -> None:
    if not isinstance(request_id, str) or not request_id.strip():
        raise IpcContractError("request_id must be a non-empty string")
    if version != IPC_VERSION:
        raise IpcContractError(f"unsupported IPC version: {version!r}")
