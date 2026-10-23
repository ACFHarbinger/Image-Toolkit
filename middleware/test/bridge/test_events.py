from __future__ import annotations

import pytest

from middleware.src.bridge.catalog import catalog
from middleware.src.bridge.envelope import BridgeAppError, FrameValidationError
from middleware.src.bridge.events import bridge_state_event, build_event, job_event, validate_event

TABLE = catalog()


def test_build_event_validates_and_fills_defaults() -> None:
    frame = job_event("job-1", "running", seq=1, progress={"done": 0, "total": 10})
    assert frame["channel"] == "jobs"
    assert frame["durable"] is True  # durable_default from methods.toml
    assert TABLE.validate_event_envelope(frame) == []
    assert TABLE.validate_event_payload("jobs", frame["payload"]) == []


def test_durable_default_from_methods_toml() -> None:
    frame = build_event("bridge", 1, "fact", {"state": "ready"})
    assert frame["durable"] is False  # bridge channel is non-durable


def test_bridge_state_event_restarts_contract() -> None:
    down = bridge_state_event("down", seq=1)
    ready = bridge_state_event("ready", seq=2)
    assert down["payload"] == {"state": "down"}
    assert ready["payload"] == {"state": "ready"}
    validate_event(down)
    validate_event(ready)


def test_validate_event_rejects_unknown_channel() -> None:
    with pytest.raises(FrameValidationError) as exc_info:
        validate_event({"channel": "telemetry", "seq": 1, "kind": "fact", "durable": False, "ts": "t", "payload": {}})
    assert exc_info.value.app_error.code == "bridge.unknown_channel"


def test_validate_event_enforces_envelope_enum_and_seq() -> None:
    base = {"channel": "bridge", "seq": 1, "kind": "fact", "durable": False, "ts": "t", "payload": {"state": "ready"}}
    bad_kind = dict(base, kind="rumour")
    with pytest.raises(FrameValidationError):
        validate_event(bad_kind)
    zero_seq = dict(base, seq=0)
    with pytest.raises(FrameValidationError):
        validate_event(zero_seq)


def test_validate_event_enforces_payload_schema() -> None:
    frame = {
        "channel": "jobs",
        "seq": 1,
        "kind": "fact",
        "durable": True,
        "ts": "t",
        "payload": {"job_id": "j1", "state": "running", "extra": True},
    }
    with pytest.raises(FrameValidationError):
        validate_event(frame)


def test_build_event_rejects_invalid_payload_loudly() -> None:
    with pytest.raises(BridgeAppError) as exc_info:
        build_event("bridge", 1, "fact", {"state": "sideways"})
    assert exc_info.value.code == "bridge.invalid_event"
    assert exc_info.value.details["channel"] == "bridge"


def test_events_ts_is_iso8601() -> None:
    frame = build_event("bridge", 1, "fact", {"state": "ready"})
    assert frame["ts"].startswith("20")
    assert "T" in frame["ts"]
