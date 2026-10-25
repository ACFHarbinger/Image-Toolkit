"""Live-sidecar protocol tests: subprocess over real pipes (W0-12, #876)."""

from __future__ import annotations

import json
import subprocess
import sys
import time

import pytest

from .client import REPO_ROOT, SidecarClient


@pytest.fixture
def sidecar():
    client = SidecarClient()
    try:
        yield client
    finally:
        client.kill()


def _error(frame: dict) -> dict:
    return frame["error"]["data"]


def test_handshake_accept(sidecar: SidecarClient) -> None:
    response = sidecar.handshake()
    result = response["result"]
    assert result["protocol"] == "image-toolkit-bridge"
    assert result["compatibility"] == {"min": "1.0.0", "max": "1.0.0"}
    assert sorted(result["capabilities"]) == [
        "cloud_jobs",
        "cloud_offer",
        "convert",
        "drive_sync",
        "extractor",
        "jobs",
        "library",
        "library_admin",
        "library_preview",
        "media_loader",
        "merge",
        "scan",
        "settings",
        "similarity",
        "system",
    ]


def test_handshake_version_mismatch_rejected(sidecar: SidecarClient) -> None:
    response = sidecar.handshake(version="0.0.1")
    error = _error(response)
    assert error["code"] == "bridge.version_mismatch"
    assert error["retryable"] is False
    # The gate stays closed after a failed handshake.
    sidecar.send({"jsonrpc": "2.0", "id": 2, "method": "system.ping", "params": {}})
    assert "handshake required" in _error(sidecar.read_response())["details"]["reason"]


def test_handshake_protocol_mismatch_rejected(sidecar: SidecarClient) -> None:
    response = sidecar.handshake(protocol="other-protocol")
    assert _error(response)["code"] == "bridge.protocol_mismatch"


def test_ping_after_handshake(sidecar: SidecarClient) -> None:
    sidecar.handshake()
    sidecar.send({"jsonrpc": "2.0", "id": 2, "method": "system.ping", "params": {}})
    assert sidecar.read_response()["result"] == {"ok": True}


def test_request_before_handshake_rejected(sidecar: SidecarClient) -> None:
    sidecar.send({"jsonrpc": "2.0", "id": 1, "method": "jobs.list", "params": {}})
    error = _error(sidecar.read_response())
    assert error["code"] == "bridge.invalid_request"
    assert "handshake required" in error["details"]["reason"]


def test_unknown_method(sidecar: SidecarClient) -> None:
    sidecar.handshake()
    sidecar.send({"jsonrpc": "2.0", "id": 2, "method": "nosuch.method", "params": {}})
    response = sidecar.read_response()
    assert response["error"]["code"] == -32601
    assert _error(response)["code"] == "bridge.method_not_found"


def test_malformed_frame_parse_error_then_recovers(sidecar: SidecarClient) -> None:
    sidecar.send_raw("this is not json")
    response = sidecar.read_response()
    assert response["id"] is None
    assert response["error"]["code"] == -32700
    assert _error(response)["code"] == "bridge.parse_error"
    # The loop survives a bad line and answers the next frame.
    assert sidecar.handshake()["result"]["protocol"] == "image-toolkit-bridge"


def test_invalid_envelope_rejected(sidecar: SidecarClient) -> None:
    sidecar.send({"jsonrpc": "2.0", "id": 1, "method": "System.ping"})  # bad method pattern
    assert _error(sidecar.read_response())["code"] == "bridge.invalid_request"


def test_invalid_params_rejected(sidecar: SidecarClient) -> None:
    sidecar.handshake()
    sidecar.send({"jsonrpc": "2.0", "id": 2, "method": "jobs.submit", "params": {"kind": "x"}})
    error = _error(sidecar.read_response())
    assert error["code"] == "bridge.invalid_params"
    assert error["retryable"] is True


def test_jobs_round_trip_and_events(sidecar: SidecarClient) -> None:
    sidecar.handshake()
    sidecar.send({"jsonrpc": "2.0", "id": 1, "method": "jobs.submit", "params": {"kind": "demo", "spec": {"a": 1}}})
    event = sidecar.read_frame()  # job events are emitted before the response
    assert event["channel"] == "jobs"
    assert event["durable"] is True
    assert event["payload"]["state"] == "queued"
    job_id = sidecar.read_response()["result"]["job_id"]
    assert event["payload"]["job_id"] == job_id

    sidecar.send({"jsonrpc": "2.0", "id": 2, "method": "jobs.status", "params": {"job_id": job_id}})
    assert sidecar.read_response()["result"] == {"job_id": job_id, "kind": "demo", "state": "queued"}

    sidecar.send({"jsonrpc": "2.0", "id": 3, "method": "jobs.cancel", "params": {"job_id": job_id}})
    event = sidecar.read_frame()
    assert event["payload"] == {"job_id": job_id, "state": "cancelled"}
    assert sidecar.read_response()["result"] == {"ok": True}

    # Idempotent: cancelling the terminal job again is a no-op success.
    sidecar.send({"jsonrpc": "2.0", "id": 4, "method": "jobs.cancel", "params": {"job_id": job_id}})
    assert sidecar.read_response()["result"] == {"ok": True}

    sidecar.send({"jsonrpc": "2.0", "id": 5, "method": "jobs.list", "params": {"states": ["cancelled"]}})
    assert [job["job_id"] for job in sidecar.read_response()["result"]["jobs"]] == [job_id]


def test_cancel_unknown_job_is_not_found(sidecar: SidecarClient) -> None:
    sidecar.handshake()
    sidecar.send({"jsonrpc": "2.0", "id": 1, "method": "jobs.cancel", "params": {"job_id": "nope"}})
    error = _error(sidecar.read_response())
    assert error["code"] == "jobs.not_found"
    assert error["details"]["job_id"] == "nope"


def test_stdout_purity(sidecar: SidecarClient) -> None:
    """Every stdout line is a framed response/event; diagnostics stay on stderr."""
    sidecar.send_raw("garbage line")
    first = json.loads(sidecar.read_line())
    assert first["id"] is None and first["error"]["data"]["code"] == "bridge.parse_error"
    sidecar.handshake()  # consumes its own response
    sidecar.send({"jsonrpc": "2.0", "id": 1, "method": "jobs.status", "params": {"job_id": "nope"}})
    sidecar.send({"jsonrpc": "2.0", "id": 2, "method": "system.ping", "params": {}})
    for expected_id in (1, 2):
        line = sidecar.read_line()
        frame = json.loads(line)  # raises unless the line is one JSON object
        assert frame.get("id") == expected_id
        assert "jsonrpc" in frame or "channel" in frame
    sidecar.close()
    stderr = sidecar.stderr_text()
    assert stderr == ""  # the server reports errors in-band; stderr stays silent


def test_no_torch_at_startup() -> None:
    code = (
        "import sys;"
        "import middleware.src.sidecar;"
        "import middleware.src.sidecar.__main__;"
        "heavy = [m for m in ('torch', 'cv2') if m in sys.modules];"
        "print(heavy);"
        "sys.exit(1 if heavy else 0)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr


def test_heartbeat_file(tmp_path) -> None:
    client = SidecarClient("--data-dir", str(tmp_path))
    try:
        heartbeat = tmp_path / "supervisor" / "sidecar.heartbeat"
        for _ in range(100):
            if heartbeat.exists():
                break
            time.sleep(0.05)
        payload = json.loads(heartbeat.read_text(encoding="utf-8"))
        assert payload["role"] == "sidecar"
        assert payload["pid"] == client.proc.pid
    finally:
        client.kill()
