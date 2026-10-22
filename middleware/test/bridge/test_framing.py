from __future__ import annotations

import io
import json

import pytest

from middleware.src.bridge.envelope import BridgeAppError
from middleware.src.bridge.framing import encode_frame, iter_frames, write_frame


def test_encode_frame_is_single_line() -> None:
    frame = encode_frame({"jsonrpc": "2.0", "id": 1, "method": "system.ping"})
    line = frame.decode("utf-8")
    assert line.endswith("\n")
    assert line.count("\n") == 1
    assert json.loads(line) == {"jsonrpc": "2.0", "id": 1, "method": "system.ping"}


def test_encode_frame_rejects_non_object() -> None:
    with pytest.raises(TypeError):
        encode_frame([1, 2])  # type: ignore[arg-type]


def test_encode_frame_rejects_nan() -> None:
    with pytest.raises(TypeError):
        encode_frame({"result": float("nan")})


def test_encode_frame_rejects_embedded_newline() -> None:
    # json.dumps escapes control characters, so the wire line stays single-line
    frame = encode_frame({"method": "sys\ntem.ping"})
    assert frame.decode("utf-8").count("\n") == 1


def test_write_and_iter_roundtrip() -> None:
    stream = io.StringIO()
    write_frame(stream, {"jsonrpc": "2.0", "id": "a", "method": "system.ping"})
    write_frame(stream, {"jsonrpc": "2.0", "id": "b", "method": "system.ping"})
    frames = list(iter_frames(io.StringIO(stream.getvalue())))
    assert [frame["id"] for frame in frames] == ["a", "b"]


def test_iter_frames_skips_blank_lines() -> None:
    frames = list(iter_frames(io.StringIO('\n  \n{"id": 1}\n\n')))
    assert len(frames) == 1


def test_iter_frames_parse_error_is_app_error() -> None:
    with pytest.raises(BridgeAppError) as exc_info:
        list(iter_frames(io.StringIO("not json\n")))
    assert exc_info.value.code == "bridge.parse_error"
    assert exc_info.value.retryable is False


def test_iter_frames_rejects_non_object_line() -> None:
    with pytest.raises(BridgeAppError) as exc_info:
        list(iter_frames(io.StringIO("[1, 2]\n")))
    assert exc_info.value.code == "bridge.parse_error"
