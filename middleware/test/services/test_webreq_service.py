"""Unit tests for the WebRequests service layer, handlers, and sidecar dispatch (B-02 / #907)."""

from __future__ import annotations

import io
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from middleware.src.events import Observable
from middleware.src.services.base import CommandValidationError
from middleware.src.services.webreq import (
    ActionItem,
    ExecuteCommand,
    RequestItem,
    SequenceCommand,
    WebRequestsService,
    WebRequestsServiceProtocol,
)
from middleware.src.sidecar.handlers.webreq import (
    handle_webreq_execute,
    handle_webreq_sequence,
)


def test_webreq_service_protocol_conformance():
    service = WebRequestsService()
    assert isinstance(service, WebRequestsServiceProtocol)


def test_webreq_execute_url_validation():
    service = WebRequestsService()
    with pytest.raises(CommandValidationError):
        service.execute(ExecuteCommand(url="   "))


def test_webreq_execute_mock_success():
    service = WebRequestsService()
    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_resp.msg = "OK"
    mock_resp.headers = {"Content-Type": "application/json", "Server": "test"}
    mock_resp.read.return_value = b'{"status": "healthy"}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = service.execute(
            ExecuteCommand(
                url="https://api.example.com/health",
                method="GET",
                headers={"Authorization": "Bearer token"},
                timeout_seconds=5,
            )
        )

    assert res.status_code == 200
    assert res.status_text == "OK"
    assert res.content_type == "application/json"
    assert "healthy" in res.body
    assert res.duration_ms >= 0
    assert res.error is None


def test_webreq_execute_http_error():
    service = WebRequestsService()
    err = urllib.error.HTTPError(
        url="https://api.example.com/missing",
        code=404,
        msg="Not Found",
        hdrs={"Content-Type": "text/plain"},
        fp=io.BytesIO(b"Resource does not exist"),
    )

    with patch("urllib.request.urlopen", side_effect=err):
        res = service.execute(ExecuteCommand(url="https://api.example.com/missing"))

    assert res.status_code == 404
    assert res.status_text == "Not Found"
    assert "Resource does not exist" in res.body
    assert "HTTP 404" in (res.error or "")


def test_webreq_execute_connection_error():
    service = WebRequestsService()
    err = urllib.error.URLError("Connection refused")

    with patch("urllib.request.urlopen", side_effect=err):
        res = service.execute(ExecuteCommand(url="https://offline.host/api"))

    assert res.status_code == 0
    assert res.status_text == "Connection Error"
    assert "Connection refused" in (res.error or "")


class MockLogic:
    """Mock WebRequestsLogic simulating C++ callback events."""

    def __init__(self, config: dict):
        self.config = config
        self.on_status = Observable()
        self.on_error = Observable()
        self.on_finished = Observable()

    def run(self):
        self.on_status.publish("Starting mock sequence")
        for i, _ in enumerate(self.config.get("requests", [])):
            self.on_status.publish(f"--- Request {i + 1}/1: [GET] ---")
            self.on_status.publish("Request complete. Status: 200")
            for act in self.config.get("actions", []):
                if act.get("type") == "Print Response Status Code":
                    self.on_status.publish("  > Action: Status Code: 200")
        self.on_status.publish("--- All requests finished. ---")
        self.on_finished.publish("All requests finished.")


def test_webreq_sequence_with_mock_logic():
    service = WebRequestsService(logic_cls=MockLogic)
    cmd = SequenceCommand(
        base_url="https://api.example.com",
        requests=[RequestItem(type="GET", param="/status")],
        actions=[ActionItem(type="Print Response Status Code")],
    )
    result = service.sequence(cmd)

    assert result.status == "completed"
    assert result.total_requests == 1
    assert result.completed_requests == 1
    assert len(result.items) == 1
    assert result.items[0].status_code == 200
    assert any("Action: Status Code: 200" in log for log in result.logs)


def test_webreq_fallback_sequence_and_save_action(tmp_path: Path):
    target_file = tmp_path / "downloads" / "output.txt"
    service = WebRequestsService(logic_cls="fallback")

    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_resp.msg = "OK"
    mock_resp.headers = {"Content-Type": "text/plain"}
    mock_resp.read.return_value = b"Downloaded text payload"
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        cmd = SequenceCommand(
            base_url="https://example.com",
            requests=[RequestItem(type="GET", param="/data.txt")],
            actions=[
                ActionItem(type="Print Response Content (Text)"),
                ActionItem(type="Save Response Content (Binary)", param=str(target_file)),
            ],
        )
        res = service.sequence(cmd)

    assert res.status == "completed"
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == "Downloaded text payload"
    assert res.items[0].saved_path == str(target_file)


class _SplitStatusLogic:
    """Native stand-in: a 201 followed by a 404, each inside its own boundary."""

    def __init__(self, config: dict):
        self.config = config
        self.on_status = Observable()
        self.on_error = Observable()
        self.on_finished = Observable()

    def run(self) -> None:
        self.on_status.publish("--- Request 1/2: [GET] ---")
        self.on_status.publish("Request complete. Status: 201")
        self.on_status.publish("  > Action: Response content saved to /tmp/one.bin")
        self.on_status.publish("--- Request 2/2: [GET] ---")
        self.on_status.publish("Request complete. Status: 404")
        self.on_error.publish("Request failed: HTTP 404")
        self.on_finished.publish("done")


def test_sequence_logs_stay_with_their_request():
    service = WebRequestsService(logic_cls=_SplitStatusLogic)
    result = service.sequence(
        SequenceCommand(
            base_url="https://api.example.com",
            requests=[RequestItem(type="GET", param="/created"), RequestItem(type="GET")],
        )
    )
    assert result.items[0].status_code == 201
    assert result.items[0].error is None
    assert result.items[0].saved_path == "/tmp/one.bin"
    assert result.items[1].status_code == 404
    assert result.items[1].error == "HTTP 404"
    assert result.items[1].saved_path is None


class _RejectNative:
    def __init__(self, config: dict):
        raise AssertionError("native executor must not run")


def _ok_response(payload: bytes) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_resp.msg = "OK"
    mock_resp.headers = {"Content-Type": "application/octet-stream"}
    mock_resp.read.return_value = payload
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


def test_sequence_routes_headers_and_unsupported_methods_to_python():
    seen: dict[str, object] = {}

    def fake_urlopen(req, timeout=0):
        seen["method"] = req.get_method()
        seen["auth"] = req.get_header("Authorization")
        seen["body"] = req.data
        return _ok_response(b"patched")

    service = WebRequestsService(logic_cls=_RejectNative)
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = service.sequence(
            SequenceCommand(
                base_url="https://api.example.com/items",
                requests=[RequestItem(type="PATCH", param='{"n": 1}', headers={"Authorization": "Bearer t"})],
            )
        )

    assert seen["method"] == "PATCH"
    assert seen["auth"] == "Bearer t"
    assert seen["body"] == b'{"n": 1}'
    assert result.items[0].status_code == 200
    assert result.items[0].error is None


def test_fallback_save_writes_complete_raw_bytes(tmp_path: Path):
    raw = b"\xff" * 70_000
    target = tmp_path / "image.bin"
    service = WebRequestsService(logic_cls="fallback")
    with patch("urllib.request.urlopen", return_value=_ok_response(raw)):
        result = service.sequence(
            SequenceCommand(
                base_url="https://example.com/pic.bin",
                requests=[RequestItem(type="GET")],
                actions=[ActionItem(type="Save Response Content (Binary)", param=str(target))],
            )
        )
    assert target.read_bytes() == raw
    assert result.items[0].saved_path == str(target)
    assert len(result.logs) > 0


def test_post_body_and_custom_timeout_skip_the_native_parser():
    seen: list[dict[str, object]] = []

    def fake_urlopen(req, timeout=0):
        seen.append({"method": req.get_method(), "data": req.data, "timeout": timeout})
        return _ok_response(b"ok")

    service = WebRequestsService(logic_cls=_RejectNative)
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        service.sequence(
            SequenceCommand(
                base_url="https://api.example.com/items",
                requests=[RequestItem(type="POST", param='{"a":1}')],
                timeout_seconds=30,
            )
        )
        service.sequence(
            SequenceCommand(
                base_url="https://api.example.com/items",
                requests=[RequestItem(type="POST", param="a:1,b:2")],
            )
        )
        service.sequence(
            SequenceCommand(
                base_url="https://api.example.com/slow",
                requests=[RequestItem(type="GET", param="/slow")],
                timeout_seconds=5,
            )
        )

    assert seen[0] == {"method": "POST", "data": b'{"a":1}', "timeout": 30}
    assert seen[1] == {"method": "POST", "data": b"a:1,b:2", "timeout": 15}
    assert seen[2]["method"] == "GET"
    assert seen[2]["timeout"] == 5
    assert seen[2]["data"] is None


def test_execute_preview_does_not_replace_raw_body():
    raw = b"\xff" * 70_000
    service = WebRequestsService()
    with patch("urllib.request.urlopen", return_value=_ok_response(raw)):
        result = service.execute(ExecuteCommand(url="https://example.com/pic.bin"))
    assert result.raw_body == raw
    assert result.body == raw[:65536].decode("utf-8", errors="replace")
    assert len(result.body) < len(raw)


def test_sidecar_handlers_dispatch():
    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_resp.msg = "OK"
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.read.return_value = b'{"ok": true}'
    mock_resp.__enter__.return_value = mock_resp

    service = WebRequestsService(logic_cls=MockLogic)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        # Test execute handler
        exec_res = handle_webreq_execute(
            service,
            {"url": "https://api.example.com/test", "method": "GET"},
        )
        assert exec_res["status_code"] == 200
        assert "ok" in exec_res["body"]

        # Test sequence handler
        seq_res = handle_webreq_sequence(
            service,
            {
                "base_url": "https://api.example.com",
                "requests": [{"type": "GET", "param": "/test"}],
                "actions": [{"type": "Print Response Status Code"}],
            },
        )
        assert seq_res["status"] == "completed"
        assert seq_res["total_requests"] == 1
        assert len(seq_res["items"]) == 1
