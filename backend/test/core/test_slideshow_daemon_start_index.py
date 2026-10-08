"""Verify slideshow_daemon starts from the active wallpaper in queue."""

from __future__ import annotations

import json
from unittest.mock import patch

from backend.src.utils.display import slideshow_daemon


def test_slideshow_daemon_starts_at_active_wallpaper(tmp_path, monkeypatch):
    """When current_paths has an active wallpaper, monitor_state index should match that wallpaper."""
    test_queue = ["/img1.png", "/img2.png", "/img3.png"]
    cfg = {
        "running": True,
        "interval_seconds": 30,
        "playback_order": "Sequential",
        "style": "Fill",
        "use_video_runtime_interval": False,
        "monitor_queues": {"0": test_queue},
        "current_paths": {"0": "/img3.png"},
        "monitor_geometries": {"0": {"x": 0, "y": 0, "width": 1920, "height": 1080}},
    }

    config_path = tmp_path / "daemon.json"
    pid_path = tmp_path / "daemon.pid"
    config_path.write_text(json.dumps(cfg))

    applied = []

    def fake_apply(monitor_state, de, qdbus, raw_style, monitors):
        applied.append(dict(monitor_state))

    monkeypatch.setattr(slideshow_daemon, "DAEMON_CONFIG_PATH", config_path)
    monkeypatch.setattr(slideshow_daemon, "PID_PATH", pid_path)
    monkeypatch.setattr(slideshow_daemon, "_apply_all", fake_apply)
    monkeypatch.setattr(slideshow_daemon, "_is_session_locked", lambda: False)
    monkeypatch.setattr(slideshow_daemon, "time", type("MockTime", (), {"sleep": lambda s: (_ for _ in ()).throw(KeyboardInterrupt()), "time": lambda: 1000.0}))

    try:
        slideshow_daemon.run()
    except KeyboardInterrupt:
        pass

    assert len(applied) >= 1
    state_0 = applied[0]["0"]
    assert state_0["index"] == 2
    assert state_0["paths"][state_0["index"]] == "/img3.png"


def test_slideshow_daemon_reverse_sequential_starts_at_active(tmp_path, monkeypatch):
    """Reverse sequential should reverse the order but still start at active wallpaper."""
    test_queue = ["/img1.png", "/img2.png", "/img3.png"]
    cfg = {
        "running": True,
        "interval_seconds": 30,
        "playback_order": "Reverse Sequential",
        "style": "Fill",
        "use_video_runtime_interval": False,
        "monitor_queues": {"0": test_queue},
        "current_paths": {"0": "/img2.png"},
        "monitor_geometries": {"0": {"x": 0, "y": 0, "width": 1920, "height": 1080}},
    }

    config_path = tmp_path / "daemon.json"
    pid_path = tmp_path / "daemon.pid"
    config_path.write_text(json.dumps(cfg))

    applied = []

    def fake_apply(monitor_state, de, qdbus, raw_style, monitors):
        applied.append(dict(monitor_state))

    monkeypatch.setattr(slideshow_daemon, "DAEMON_CONFIG_PATH", config_path)
    monkeypatch.setattr(slideshow_daemon, "PID_PATH", pid_path)
    monkeypatch.setattr(slideshow_daemon, "_apply_all", fake_apply)
    monkeypatch.setattr(slideshow_daemon, "_is_session_locked", lambda: False)
    monkeypatch.setattr(slideshow_daemon, "time", type("MockTime", (), {"sleep": lambda s: (_ for _ in ()).throw(KeyboardInterrupt()), "time": lambda: 1000.0}))

    try:
        slideshow_daemon.run()
    except KeyboardInterrupt:
        pass

    assert len(applied) >= 1
    state_0 = applied[0]["0"]
    assert state_0["paths"][state_0["index"]] == "/img2.png"
