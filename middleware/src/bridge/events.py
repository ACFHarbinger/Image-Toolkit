"""Event frames: build + validate (W0-11, #875).

The EventHub (#878) folds decoded frames; this module is where frames are
built and where full JSON-Schema validation happens (the hub's TS guard is
deliberately minimal). Envelope: ``contracts/schemas/envelope/event.json``
plus the channel's payload schema from ``methods.toml``. The ``bridge``
channel carries the supervisor restart contract: ``bridge.down`` then
``bridge.ready`` around sidecar restarts.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from .catalog import Catalog, catalog
from .envelope import BridgeAppError, FrameValidationError, _app_error_from_schema_errors

__all__ = ["build_event", "validate_event", "bridge_state_event", "job_event"]


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def build_event(
    channel: str,
    seq: int,
    kind: str,
    payload: dict[str, Any],
    *,
    durable: bool | None = None,
    ts: str | None = None,
    table: Catalog | None = None,
) -> dict[str, Any]:
    """Build and validate one event frame.

    ``durable`` defaults to the channel's ``durable_default`` from
    methods.toml. Raises ``BridgeAppError`` describing the violated
    constraint (envelope or payload schema) — producers never emit an
    invalid frame silently.
    """
    table = table or catalog()
    route = table.channels.get(channel)
    if route is None:
        raise BridgeAppError("bridge.unknown_channel", details={"channel": channel})
    if durable is None:
        durable = route.durable_default
    frame: dict[str, Any] = {
        "channel": channel,
        "seq": seq,
        "kind": kind,
        "durable": durable,
        "ts": ts or _now_iso(),
        "payload": payload,
    }
    errors = table.validate_event_envelope(frame)
    if not errors:
        errors = table.validate_event_payload(channel, payload)
    if errors:
        raise BridgeAppError(
            "bridge.invalid_event",
            details={"channel": channel, "errors": [str(error) for error in errors]},
        )
    return frame


def validate_event(frame: Any, *, table: Catalog | None = None) -> dict[str, Any]:
    """Validate an inbound event frame (envelope + channel payload)."""
    table = table or catalog()
    if not isinstance(frame, dict):
        raise FrameValidationError(
            BridgeAppError("bridge.invalid_event", details={"errors": ["frame is not an object"]})
        )
    channel = frame.get("channel")
    if not isinstance(channel, str) or channel not in table.channels:
        raise FrameValidationError(BridgeAppError("bridge.unknown_channel", details={"channel": channel}))
    errors = table.validate_event_envelope(frame)
    if not errors:
        errors = table.validate_event_payload(channel, frame.get("payload"))
    if errors:
        raise FrameValidationError(_app_error_from_schema_errors("bridge.invalid_event", errors))
    return frame


def bridge_state_event(state: str, seq: int, *, table: Catalog | None = None) -> dict[str, Any]:
    """Emit ``bridge.down`` / ``bridge.ready`` on the non-durable bridge channel."""
    return build_event("bridge", seq, "fact", {"state": state}, durable=False, table=table)


def job_event(
    job_id: str,
    state: str,
    seq: int,
    *,
    progress: dict[str, int] | None = None,
    durable: bool = True,
    table: Catalog | None = None,
) -> dict[str, Any]:
    """Emit a job state/progress fact on the durable jobs channel."""
    payload: dict[str, Any] = {"job_id": job_id, "state": state}
    if progress is not None:
        payload["progress"] = progress
    return build_event("jobs", seq, "fact", payload, durable=durable, table=table)
