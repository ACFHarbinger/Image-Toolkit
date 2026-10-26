"""extractor.snapshot returns a job id before ffmpeg work finishes."""

from __future__ import annotations

import io
import threading
from typing import Any

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.sidecar.server import SidecarServer


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


def test_snapshot_dispatch_returns_a_job_before_the_worker_finishes(monkeypatch) -> None:
    started = threading.Event()
    release = threading.Event()
    calls: list[tuple[str, float, str]] = []

    def fake_snapshot(path: str, time_seconds: float, output_path: str, **_kwargs: Any) -> dict[str, Any]:
        calls.append((path, time_seconds, output_path))
        started.set()
        assert release.wait(2)
        return {"written": True, "output_path": "/out.png", "error": ""}

    monkeypatch.setattr("middleware.src.sidecar.handlers.extractor.snapshot_frame", fake_snapshot)
    server = SidecarServer(stdout=io.StringIO())
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "extractor" in handshake["result"]["capabilities"]
    try:
        response = _request(
            server,
            "extractor.snapshot",
            {"path": "/clip.mp4", "time_seconds": 0, "output_path": "/out.png"},
            "snap",
        )
        job_id = response["result"]["job_id"]
        assert isinstance(job_id, str) and job_id
        assert "written" not in response["result"]
        assert started.wait(2)
        mid = _request(server, "jobs.status", {"job_id": job_id}, "mid")["result"]
        assert mid["state"] in {"queued", "running"}
        assert mid["kind"] == "extractor.snapshot"
    finally:
        release.set()
    status: dict[str, Any] = {}
    for _ in range(50):
        status = _request(server, "jobs.status", {"job_id": job_id}, "status")["result"]
        if status["state"] in {"completed", "failed", "cancelled"}:
            break
    assert status["state"] == "completed"
    assert status["result"] == {"written": True, "output_path": "/out.png", "error": ""}
    assert calls == [("/clip.mp4", 0.0, "/out.png")]
