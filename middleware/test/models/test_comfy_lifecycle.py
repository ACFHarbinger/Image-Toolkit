"""Lifecycle checks use a tiny HTTP server, never a model or ComfyUI process."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock

import pytest

from middleware.src.constants.comfy import ServerState
from middleware.src.models.core.comfy_manager import ComfyUIManager


@pytest.fixture
def endpoint():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"system": {}, "devices": []}).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_port
    server.shutdown()
    server.server_close()
    thread.join()


def test_attach_disconnect_preserves_external_server(endpoint):
    manager = ComfyUIManager()
    states = []
    manager.subscribe_state(states.append)
    assert manager.connect(endpoint)
    assert manager.state == ServerState.READY
    assert not manager.owns_server
    manager.stop()
    assert manager.state == ServerState.STOPPED
    assert manager.connect(endpoint)
    assert states[:3] == [ServerState.STARTING, ServerState.READY, ServerState.STOPPED]


def test_start_does_not_replace_external_connection(endpoint):
    manager = ComfyUIManager()
    manager.connect(endpoint)
    with pytest.raises(RuntimeError, match="Disconnect"):
        manager.start()


def test_disconnect_and_reconnect(endpoint, monkeypatch):
    manager = ComfyUIManager()
    manager.connect(endpoint)
    with monkeypatch.context() as patch:
        patch.setattr("urllib.request.urlopen", Mock(side_effect=OSError("lost connection")))
        assert not manager.refresh_state()
        assert manager.state == ServerState.DISCONNECTED
    assert manager.refresh_state()
    assert manager.state == ServerState.READY


def test_stop_owned_process_only():
    manager = ComfyUIManager()
    process = Mock()
    process.poll.return_value = None
    manager._process = process
    manager.stop()
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=10)
    assert not manager.owns_server
    assert manager.state == ServerState.STOPPED


def test_process_exit_is_disconnected():
    manager = ComfyUIManager()
    manager._process = Mock()
    manager._process.poll.return_value = 1
    manager._set_state(ServerState.READY)
    assert not manager.refresh_state()
    assert manager.state == ServerState.DISCONNECTED


def test_start_failure_and_cancellation(monkeypatch):
    manager = ComfyUIManager()
    monkeypatch.setattr(manager, "_port_in_use", lambda _port: False)
    monkeypatch.setattr("subprocess.Popen", Mock(side_effect=OSError("launch failed")))
    with pytest.raises(OSError):
        manager.start()
    assert manager.state == ServerState.DISCONNECTED
    cancel = threading.Event()
    cancel.set()
    assert not manager.wait_until_ready(cancel=cancel)


def test_unrelated_http_service_is_not_ready(monkeypatch):
    manager = ComfyUIManager()
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock()
    response.read.return_value = b'{"unrelated":true}'
    monkeypatch.setattr("urllib.request.urlopen", Mock(return_value=response))
    assert not manager.connect()
    assert manager.state == ServerState.DISCONNECTED


def test_managed_process_start_ready_stop(tmp_path, monkeypatch):
    """Exercise process ownership with a CPU-only HTTP stub."""
    script = tmp_path / "main.py"
    script.write_text(
        "import argparse\n"
        "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('--listen'); p.add_argument('--port', type=int)\n"
        "args = p.parse_args()\n"
        "class H(BaseHTTPRequestHandler):\n"
        " def do_GET(self):\n"
        "  self.send_response(200); self.end_headers()\n"
        "  self.wfile.write(b'{\"system\": {}, \"devices\": []}')\n"
        " def log_message(self, *args): pass\n"
        "HTTPServer((args.listen, args.port), H).serve_forever()\n"
    )
    monkeypatch.setattr("middleware.src.models.core.comfy_manager.COMFYUI_DIR", tmp_path)
    manager = ComfyUIManager()
    port = manager._find_free_port(28188)
    states = []
    manager.subscribe_state(states.append)
    try:
        assert manager.start(port) == port
        process = manager._process
        assert manager.owns_server
        assert manager.wait_until_ready(timeout=3)
        assert states == [ServerState.STARTING, ServerState.READY]
    finally:
        manager.stop()
    assert process.poll() is not None
    assert manager.state == ServerState.STOPPED


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_invalid_ports_do_not_launch_or_attach(port):
    manager = ComfyUIManager()
    with pytest.raises(ValueError):
        manager.connect(port)
    with pytest.raises(ValueError):
        manager.start(port)
    assert not manager.owns_server
