"""Slideshow daemon liveness: stale running flags must not survive a dead pid."""

from __future__ import annotations

import json
import os

from backend.src.utils.display.monitor_slideshow_daemon import (
    daemon_is_live,
    is_pid_alive,
    mark_stopped,
)


class TestPidAlive:
    def test_current_process_is_alive(self):
        assert is_pid_alive(os.getpid()) is True

    def test_zero_and_negative_are_dead(self):
        assert is_pid_alive(0) is False
        assert is_pid_alive(-1) is False

    def test_unused_pid_is_dead(self):
        assert is_pid_alive(2**22) is False


class TestDaemonIsLive:
    def test_missing_config(self):
        assert daemon_is_live(None) is False

    def test_running_without_pid_is_stale(self):
        assert daemon_is_live({"running": True, "monitor_id": "0"}) is False

    def test_running_with_dead_pid_is_stale(self):
        assert daemon_is_live({"running": True, "pid": 2**22}) is False

    def test_running_with_live_pid(self):
        assert daemon_is_live({"running": True, "pid": os.getpid()}) is True

    def test_not_running_even_with_live_pid(self):
        assert daemon_is_live({"running": False, "pid": os.getpid()}) is False


class TestMarkStopped:
    def test_clears_running_and_pid(self, tmp_path, monkeypatch):
        from backend.src.utils.display import monitor_slideshow_daemon as daemon

        path = tmp_path / "daemon.json"
        monkeypatch.setattr(daemon, "MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH", path)
        mark_stopped({"running": True, "pid": 123, "monitor_id": "0"})
        data = json.loads(path.read_text())
        assert data["running"] is False
        assert "pid" not in data
        assert data["monitor_id"] == "0"


class TestStartupLiveness:
    def test_stale_flag_does_not_restore_active_monitor(self, tmp_path, monkeypatch):
        from backend.src.utils.display import monitor_slideshow_daemon as daemon
        from gui.src.elements.core.wallpaper_tab.monitor_display_subtab._slideshow_daemon import (
            _SlideshowDaemonMixin,
        )

        path = tmp_path / "daemon.json"
        path.write_text(json.dumps({"running": True, "monitor_id": "3", "pid": 2**22}))
        monkeypatch.setattr(daemon, "MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH", path)
        monkeypatch.setattr(
            "gui.src.elements.core.wallpaper_tab.monitor_display_subtab._slideshow_daemon.MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH",
            path,
        )

        class Fake(_SlideshowDaemonMixin):
            def __init__(self):
                self._daemon_active_monitor_id = "stale"
                self._inapp_active_monitor_id = None

            def _update_slideshow_buttons(self):
                pass

            def _update_queue_status_label(self):
                pass

        tab = Fake()
        tab._check_daemon_status_on_startup()
        assert tab._daemon_active_monitor_id is None
        saved = json.loads(path.read_text())
        assert saved["running"] is False

    def test_live_pid_restores_monitor(self, tmp_path, monkeypatch):
        from backend.src.utils.display import monitor_slideshow_daemon as daemon
        from gui.src.elements.core.wallpaper_tab.monitor_display_subtab._slideshow_daemon import (
            _SlideshowDaemonMixin,
        )

        path = tmp_path / "daemon.json"
        path.write_text(
            json.dumps({"running": True, "monitor_id": "2", "pid": os.getpid()})
        )
        monkeypatch.setattr(daemon, "MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH", path)
        monkeypatch.setattr(
            "gui.src.elements.core.wallpaper_tab.monitor_display_subtab._slideshow_daemon.MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH",
            path,
        )

        class Fake(_SlideshowDaemonMixin):
            def __init__(self):
                self._daemon_active_monitor_id = None
                self._inapp_active_monitor_id = None
                self.buttons = 0

            def _update_slideshow_buttons(self):
                self.buttons += 1

            def _update_queue_status_label(self):
                pass

        tab = Fake()
        tab._check_daemon_status_on_startup()
        assert tab._daemon_active_monitor_id == "2"
        assert tab.buttons == 1
