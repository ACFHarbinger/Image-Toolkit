from __future__ import annotations

import io
import json
from typing import Any

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.sidecar.server import SidecarServer


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str = "req-1") -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


def _handshake(server: SidecarServer, version: str = "1.0.0") -> dict[str, Any]:
    return _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": version}},
        "handshake",
    )


def test_handshake_is_required_before_commands() -> None:
    server = SidecarServer(stdout=io.StringIO())
    response = _request(server, "system.ping", {})
    error = response["error"]["data"]
    assert error["code"] == "bridge.invalid_request"
    assert "handshake required" in error["details"]["reason"]


def test_handshake_result_and_ping_validate() -> None:
    server = SidecarServer(stdout=io.StringIO())
    handshake = _handshake(server)
    result = handshake["result"]
    assert result["protocol"] == PROTOCOL_NAME
    assert result["compatibility"] == {"min": "1.0.0", "max": "1.0.0"}
    assert set(result["capabilities"]) == {"system", "jobs", "convert", "cloud_offer"}
    assert _request(server, "system.ping", {}, "ping")["result"] == {"ok": True}


def test_handshake_rejects_wrong_protocol_and_version() -> None:
    server = SidecarServer(stdout=io.StringIO())
    wrong_protocol = _request(
        server,
        "system.handshake",
        {"protocol": "other", "client": {"name": "pytest", "version": "1.0.0"}},
    )
    assert wrong_protocol["error"]["data"]["code"] == "bridge.protocol_mismatch"

    wrong_version = _handshake(server, version="9.9.9")
    assert wrong_version["error"]["data"]["code"] == "bridge.version_mismatch"
    assert server.handshaken is False


def test_unknown_method_uses_bridge_error_envelope() -> None:
    server = SidecarServer(stdout=io.StringIO())
    _handshake(server)
    response = _request(server, "jobs.nope", {})
    error = response["error"]
    assert error["code"] == -32601
    assert error["data"]["code"] == "bridge.method_not_found"


def test_jobs_lifecycle_and_idempotent_cancel() -> None:
    stdout = io.StringIO()
    server = SidecarServer(stdout=stdout)
    _handshake(server)

    submitted = _request(server, "jobs.submit", {"kind": "convert", "spec": {}}, "submit")
    job_id = submitted["result"]["job_id"]
    status = _request(server, "jobs.status", {"job_id": job_id}, "status")
    assert status["result"] == {"job_id": job_id, "kind": "convert", "state": "queued"}

    cancelled = _request(server, "jobs.cancel", {"job_id": job_id}, "cancel")
    assert cancelled["result"] == {"ok": True}
    repeat = _request(server, "jobs.cancel", {"job_id": job_id}, "cancel-2")
    assert repeat["result"] == {"ok": True}
    assert _request(server, "jobs.status", {"job_id": job_id}, "status-2")["result"]["state"] == "cancelled"

    listed = _request(server, "jobs.list", {"states": ["cancelled"]}, "list")
    assert [job["job_id"] for job in listed["result"]["jobs"]] == [job_id]

    event_lines = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [frame["payload"]["state"] for frame in event_lines] == ["queued", "cancelled"]
    assert [frame["seq"] for frame in event_lines] == [1, 2]
    assert all(frame["channel"] == "jobs" and frame["durable"] is True for frame in event_lines)


def test_unknown_job_is_not_found() -> None:
    server = SidecarServer(stdout=io.StringIO())
    _handshake(server)
    response = _request(server, "jobs.status", {"job_id": "missing"})
    assert response["error"]["data"] == {
        "code": "jobs.not_found",
        "retryable": False,
        "message_key": "bridge.errors.not_found",
        "details": {"job_id": "missing"},
    }


def test_invalid_params_do_not_leak_exception_text() -> None:
    server = SidecarServer(stdout=io.StringIO())
    _handshake(server)
    response = _request(server, "jobs.submit", {"kind": "convert"})
    assert response["error"]["data"]["code"] == "bridge.invalid_params"
    assert "secret" not in json.dumps(response)


def test_serve_stdout_carries_only_json_frames() -> None:
    stdin = io.StringIO(
        '{"jsonrpc":"2.0","id":"h","method":"system.handshake","params":{"protocol":"image-toolkit-bridge","client":{"name":"pytest","version":"1.0.0"}}}\n'
        "not json\n"
        '{"jsonrpc":"2.0","id":"p","method":"system.ping","params":{}}\n'
    )
    stdout = io.StringIO()
    stderr = io.StringIO()
    SidecarServer(stdin=stdin, stdout=stdout, stderr=stderr).serve()
    lines = stdout.getvalue().splitlines()
    assert len(lines) == 3
    frames = [json.loads(line) for line in lines]
    assert frames[0]["id"] == "h"
    assert frames[1]["error"]["data"]["code"] == "bridge.parse_error"
    assert frames[2]["result"] == {"ok": True}
    assert stderr.getvalue() == ""


def test_fitting_vram_is_not_offered() -> None:
    server = SidecarServer(stdout=io.StringIO())
    _handshake(server)
    result = _request(
        server,
        "cloud_offer.prefill",
        {"owner": "generate", "estimated_gb": 1.0, "device_gb": 10.0},
    )["result"]
    assert result["offered"] is False
    assert result["submitted"] is False
    assert result["job_id"] == ""


def test_vram_refusal_prefills_without_submitting() -> None:
    server = SidecarServer(stdout=io.StringIO())
    _handshake(server)
    result = _request(
        server,
        "cloud_offer.prefill",
        {"owner": "train-lora", "estimated_gb": 9.1, "device_gb": 10.0},
    )["result"]
    assert result["offered"] is True
    assert result["submitted"] is False
    assert result["kind"] == "lora_train"
    assert result["vram_gb_min"] == 9.1
    assert result["provider"] == "gcp"
    assert result["job_id"].startswith("cj-")
    assert "GPU admission refused" in result["reason"]
