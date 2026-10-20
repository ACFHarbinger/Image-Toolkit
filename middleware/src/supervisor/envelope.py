"""Bridge events and the session-request error envelope (Mistral M6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PROTOCOL_VERSION = 1

BRIDGE_DOWN = "bridge.down"
BRIDGE_READY = "bridge.ready"

CODE_BRIDGE_DOWN = "bridge.down"
MESSAGE_BRIDGE_UNAVAILABLE = "bridge.unavailable"


@dataclass(frozen=True)
class ErrorEnvelope:
    """Mapped onto ``middleware.src.errors`` once HostClient exists (#875)."""

    code: str
    retryable: bool
    message_key: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "retryable": self.retryable,
            "message_key": self.message_key,
            "details": dict(self.details),
        }


def bridge_unavailable(*, sidecar_pid: int | None = None) -> ErrorEnvelope:
    details: dict[str, Any] = {}
    if sidecar_pid is not None:
        details["sidecar_pid"] = sidecar_pid
    return ErrorEnvelope(
        code=CODE_BRIDGE_DOWN,
        retryable=True,
        message_key=MESSAGE_BRIDGE_UNAVAILABLE,
        details=details,
    )


@dataclass(frozen=True)
class BridgeEvent:
    name: str
    protocol_version: int | None = None
    sidecar_pid: int | None = None
    previous_sidecar_pid: int | None = None
