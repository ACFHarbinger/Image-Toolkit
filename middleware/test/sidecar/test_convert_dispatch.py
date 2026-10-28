"""convert.convert reaches ConvertService through the sidecar dispatcher."""

from __future__ import annotations

import io
import json
import os
import queue
import threading
import time
from typing import Any

from middleware.src.bridge import PROTOCOL_NAME, Cancelled
from middleware.src.sidecar.server import SidecarServer


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


def _ready() -> SidecarServer:
    server = SidecarServer(stdout=io.StringIO())
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "convert" in handshake["result"]["capabilities"]
    return server


def test_omitted_directory_formats_include_every_supported_extension() -> None:
    from middleware.src.sidecar.handlers.convert import _batch_command

    omitted = _batch_command({"input_dir": "/in", "output_dir": "/out", "output_format": "png"})
    assert {"bmp", "gif", "tif", "tiff"} <= set(omitted.input_formats)
    tiff_only = _batch_command(
        {
            "input_dir": "/in",
            "output_dir": "/out",
            "output_format": "png",
            "input_formats": ["tiff"],
        }
    )
    assert set(tiff_only.input_formats) == {"tif", "tiff"}


def test_missing_input_is_a_validated_convert_result() -> None:
    server = _ready()
    response = _request(
        server,
        "convert.convert",
        {"input_path": "/no/such/image.png", "output_path": "/tmp/out.png", "quality": 95},
        "convert",
    )
    result = response["result"]
    assert result["success"] is False
    assert result["input_path"] == "/no/such/image.png"
    assert "does not exist" in result["error"]


def test_non_canonical_quality_is_rejected_before_dispatch() -> None:
    server = _ready()
    response = _request(
        server,
        "convert.convert",
        {"input_path": "/no/such/image.png", "output_path": "/tmp/out.png", "quality": 80},
        "convert",
    )
    assert response["error"]["data"]["code"] == "bridge.invalid_params"


def test_jpg_suffix_selects_jpeg_when_format_is_omitted(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class _FakeService:
        def convert_single(self, command):  # noqa: ANN001
            captured["format"] = command.output_format
            from middleware.src.services.convert.commands import ConvertSingleResult

            return ConvertSingleResult(command.input_path, command.output_path, True)

    monkeypatch.setattr(
        "middleware.src.sidecar.handlers.convert.ConvertService",
        lambda: _FakeService(),
    )
    server = _ready()
    response = _request(
        server,
        "convert.convert",
        {"input_path": "/pics/a.png", "output_path": "/tmp/out.jpg", "quality": 95},
        "convert",
    )
    assert response["result"]["success"] is True
    assert captured["format"] == "jpg"


def test_format_that_disagrees_with_the_suffix_is_rejected() -> None:
    server = _ready()
    response = _request(
        server,
        "convert.convert",
        {
            "input_path": "/pics/a.png",
            "output_path": "/tmp/out.jpg",
            "output_format": "png",
            "quality": 95,
        },
        "convert",
    )
    assert response["result"]["success"] is False
    assert "does not match" in response["result"]["error"]


def test_empty_batch_finishes_on_a_job(tmp_path) -> None:
    server = _ready()
    source = tmp_path / "in"
    source.mkdir()
    response = _request(
        server,
        "convert.convert_batch",
        {"input_dir": str(source), "output_dir": str(tmp_path / "out"), "output_format": "png"},
        "batch",
    )
    job_id = response["result"]["job_id"]
    status = _wait_terminal(server, job_id)
    assert status["state"] == "completed"
    assert status["result"]["total_discovered"] == 0


def test_cancel_is_answered_while_a_batch_is_still_running(tmp_path) -> None:
    started = threading.Event()
    release = threading.Event()

    def blocked(self, command, checkpoint=None):  # noqa: ANN001, ARG001
        started.set()
        release.wait(3)
        raise Cancelled("stopped")

    from middleware.src.sidecar.handlers import convert as convert_handler

    original = convert_handler.ConvertService.convert_batch
    convert_handler.ConvertService.convert_batch = blocked
    read_fd, write_fd = os.pipe()
    in_read, in_write = os.pipe()
    frames: queue.Queue[str] = queue.Queue()
    stdout = os.fdopen(write_fd, "w", encoding="utf-8")
    stdin = os.fdopen(in_read, "r", encoding="utf-8")
    client_in = os.fdopen(in_write, "w", encoding="utf-8")
    client_out = os.fdopen(read_fd, "r", encoding="utf-8")

    def pump() -> None:
        for line in client_out:
            frames.put(line)

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    server = SidecarServer(stdin=stdin, stdout=stdout)
    serve_thread = threading.Thread(target=server.serve, daemon=True)
    serve_thread.start()
    try:
        _write(
            client_in,
            "system.handshake",
            {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
            "hs",
        )
        _read_until(frames, lambda frame: frame.get("id") == "hs")
        source = tmp_path / "in"
        source.mkdir()
        _write(
            client_in,
            "convert.convert_batch",
            {"input_dir": str(source), "output_dir": str(tmp_path / "out"), "output_format": "png"},
            "batch",
        )
        accepted = _read_until(frames, lambda frame: frame.get("id") == "batch")
        assert started.wait(2)
        job_id = accepted["result"]["job_id"]
        _write(client_in, "jobs.cancel", {"job_id": job_id}, "cancel")
        cancelled = _read_until(frames, lambda frame: frame.get("id") == "cancel")
        assert cancelled["result"]["ok"] is True
    finally:
        release.set()
        convert_handler.ConvertService.convert_batch = original
        client_in.close()
        serve_thread.join(timeout=2)
        stdout.close()
        client_out.close()


def _write(stream, method: str, params: dict[str, Any], request_id: str) -> None:
    stream.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) + "\n")
    stream.flush()


def _read_until(frames: queue.Queue[str], predicate, timeout: float = 2.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            line = frames.get(timeout=0.1)
        except queue.Empty:
            continue
        frame = json.loads(line)
        if predicate(frame):
            return frame
    raise AssertionError("timed out waiting for a sidecar frame")


def _wait_terminal(server: SidecarServer, job_id: str) -> dict[str, Any]:
    status: dict[str, Any] = {}
    for _ in range(50):
        status = _request(server, "jobs.status", {"job_id": job_id}, "status")["result"]
        if status["state"] in {"completed", "failed", "cancelled"}:
            return status
        time.sleep(0.02)
    raise AssertionError(status)
