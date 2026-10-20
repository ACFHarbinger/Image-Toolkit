"""Line-delimited JSON framing over stdio (W0-11, #875).

The sidecar's stdout carries only framed protocol messages; diagnostics go
to stderr redacted (roadmap "Bridge"). A frame is one JSON object per
newline — no embedded newlines, so a supervising process can split the
stream without a length prefix.
"""

from __future__ import annotations

import json
from typing import Any, Iterator, TextIO

from .envelope import BridgeAppError

_NEWLINE = "\n"


def encode_frame(message: dict[str, Any]) -> bytes:
    """Serialize one protocol message as a single-line JSON frame."""
    if not isinstance(message, dict):
        raise TypeError("a frame is a JSON object")
    try:
        line = json.dumps(message, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"frame is not JSON-serializable: {exc}") from exc
    return (line + _NEWLINE).encode("utf-8")


def write_frame(stream: TextIO, message: dict[str, Any]) -> None:
    stream.write(encode_frame(message).decode("utf-8"))
    stream.flush()


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def iter_frames(stream: TextIO) -> Iterator[dict[str, Any]]:
    """Yield decoded frames; a non-JSON line raises a parse app error."""
    for line in stream:
        line = line.strip()
        if not line:
            continue
        try:
            frame = json.loads(line, parse_constant=_reject_constant)
        except ValueError as exc:
            raise BridgeAppError(
                "bridge.parse_error",
                retryable=False,
                details={"reason": "line is not JSON", "position": getattr(exc, "pos", 0)},
            ) from exc
        if not isinstance(frame, dict):
            raise BridgeAppError(
                "bridge.parse_error",
                retryable=False,
                details={"reason": "frame is not a JSON object"},
            )
        yield frame
