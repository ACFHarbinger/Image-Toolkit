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
