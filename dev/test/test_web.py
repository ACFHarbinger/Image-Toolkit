"""Tests for the C3 local web viewer (render functions + HTTP)."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from devtool import WorkspaceStore
from devtool.ui.web import WebServer
from devtool.ui.web.server import (
    render_compare,
    render_home,
    render_investigation,
    render_session,
)


def _session(tel: Path, pid: int) -> Path:
    path = tel / f"telemetry-{pid}.jsonl"
    path.write_text(
        json.dumps({"t": 1.0, "category": "a", "event": "x.start", "tid": 1, "tname": "Main"}) + "\n",
        encoding="utf-8",
    )
    return path


class TestRender:
    def test_home_lists_investigations_and_sessions(self, tmp_path):
        tel = tmp_path / "telemetry"
        tel.mkdir()
        _session(tel, 111)
        store = WorkspaceStore(root=tmp_path / "ws", telemetry_dir=tel)
        store.create_investigation("bug-a")
        html = render_home(store)
        assert "bug-a" in html
        assert "telemetry-111.jsonl" in html

    def test_session_timeline(self, tmp_path):
        tel = tmp_path / "telemetry"
        tel.mkdir()
        p = _session(tel, 222)
        store = WorkspaceStore(root=tmp_path / "ws", telemetry_dir=tel)
        html = render_session(store, str(p))
        assert "telemetry-222.jsonl" in html
        assert "x.start" in html

    def test_investigation_notes(self, tmp_path):
        store = WorkspaceStore(root=tmp_path)
        inv = store.create_investigation("bug-a")
        inv.append_note("hello", "deepseek")
        html = render_investigation(store, "bug-a")
        assert "hello" in html
        assert "deepseek" in html

    def test_compare_missing_image(self, tmp_path):
        store = WorkspaceStore(root=tmp_path)
        html = render_compare(store, "/nonexistent.png", "")
        assert "Evidence only" in html
        assert "missing" in html

    def test_compare_renders_images(self, tmp_path):
        png = tmp_path / "a.png"
        png.write_bytes(b"\x89PNG fake")
        store = WorkspaceStore(root=tmp_path)
        html = render_compare(store, str(png), str(png))
        assert "/artifact?path=" in html


class TestHttp:
    def test_get_home(self, tmp_path):
        store = WorkspaceStore(root=tmp_path)
        httpd = WebServer(store).serve(host="127.0.0.1", port=0)
        port = httpd.server_port
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            import urllib.request

            body = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5).read().decode()
            assert "devtool workspace" in body
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_refuses_all_interfaces(self, tmp_path):
        store = WorkspaceStore(root=tmp_path)
        with pytest.raises(ValueError):
            WebServer(store).serve(host="0.0.0.0", port=0)
