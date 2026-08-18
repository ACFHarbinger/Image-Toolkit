"""System-display daemon: locked queues + countdown survives cancel_loading."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.gui


def test_countdown_starts_before_pid_file_exists(q_app, tmp_path, monkeypatch):
    """Start click must show a timer even if the child has not written a pid yet."""
    from gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon import (
        _DaemonMixin,
    )
    from PySide6.QtWidgets import QLabel, QWidget

    path = tmp_path / ".slideshow_config.json"
    path.write_text(
        json.dumps(
            {
                "running": True,
                "interval_seconds": 30,
                "last_change_timestamp": int(__import__("time").time()),
            }
        )
    )

    class Fake(_DaemonMixin, QWidget):
        def __init__(self):
            QWidget.__init__(self)
            self.countdown_timer = None
            self.time_remaining_sec = 0
            self.interval_sec = 0
            self.countdown_label = QLabel("Timer: --:--")
            self.slideshow_group = QWidget()
            self.slideshow_group.setVisible(True)

        def update_countdown(self):
            m, s = divmod(max(0, self.time_remaining_sec), 60)
            self.countdown_label.setText(f"Timer: {m:02}:{s:02}")

    monkeypatch.setattr(
        "gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon.DAEMON_CONFIG_PATH",
        path,
    )
    monkeypatch.setattr(
        "gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon.PID_PATH",
        tmp_path / "missing.pid",
    )
    tab = Fake()
    # pyrefly: ignore [bad-argument-type]
    assert tab._is_background_daemon_process_alive() is False
    # pyrefly: ignore [bad-argument-type]
    tab._start_daemon_countdown_if_active()
    assert tab.countdown_timer is not None
    assert tab.countdown_timer.isActive()
    assert tab.countdown_label.text().startswith("Timer: ")
    assert tab.countdown_label.text() != "Timer: --:--"


def test_sync_daemon_config_keeps_locked_queues(q_app, tmp_path, monkeypatch):
    from gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon import (
        _DaemonMixin,
    )

    path = tmp_path / ".slideshow_config.json"
    path.write_text(
        json.dumps(
            {
                "running": True,
                "monitor_queues": {"0": ["/locked.jpg"]},
                "last_change_timestamp": 100,
                "monitor_history": {},
            }
        )
    )

    class Fake(_DaemonMixin):
        def __init__(self):
            self.monitor_slideshow_queues = {"0": ["/profile.jpg"]}
            self.monitor_image_paths = {}
            self.monitor_history = {}
            self.monitors = []
            self.background_type = "Slideshow"
            self.wallpaper_style = "Fill"
            self.video_style = "Scaled and Cropped"
            self.interval_min_spinbox = MagicMock()
            self.interval_min_spinbox.value.return_value = 0
            self.interval_sec_spinbox = MagicMock()
            self.interval_sec_spinbox.value.return_value = 30
            self.chk_video_runtime_interval = MagicMock()
            self.chk_video_runtime_interval.isChecked.return_value = False
            self.playback_order_combo = MagicMock()
            self.playback_order_combo.currentText.return_value = "Sequential"

        def _is_daemon_running_config(self):
            return True

    monkeypatch.setattr(
        "gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon.DAEMON_CONFIG_PATH",
        path,
    )
    # pyrefly: ignore [bad-argument-type]
    Fake()._sync_daemon_config()
    saved = json.loads(path.read_text())
    assert saved["monitor_queues"] == {"0": ["/locked.jpg"]}
    assert saved["interval_seconds"] == 30


def test_monitor_set_config_does_not_write_daemon_file(q_app, tmp_path, monkeypatch):
    from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._serialization import (
        _SerializationMixin,
    )
    from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._slideshow_daemon import (
        _SlideshowDaemonMixin,
    )

    path = tmp_path / "daemon.json"
    original = {"running": True, "monitor_id": "0", "queue": ["/a.jpg"], "pid": 1}
    path.write_text(json.dumps(original))

    class Fake(_SerializationMixin, _SlideshowDaemonMixin):
        def __init__(self):
            self._graphs = {}
            self._current_monitor_id = "0"
            self._daemon_active_monitor_id = "0"
            self._inapp_active_monitor_id = None
            self.monitor_slideshow_queues = {"0": ["/profile.jpg"]}

    monkeypatch.setattr(
        "gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._slideshow_daemon.MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH",
        path,
    )
    # pyrefly: ignore [bad-argument-type]
    Fake().set_config({"monitor_display_graphs": {}})
    assert json.loads(path.read_text()) == original


def test_start_daemon_slideshow_is_noop_when_live(q_app, tmp_path, monkeypatch):
    from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._slideshow_daemon import (
        _SlideshowDaemonMixin,
    )

    path = tmp_path / "daemon.json"
    path.write_text(
        json.dumps({"running": True, "monitor_id": "0", "queue": ["/locked.jpg"], "pid": 1})
    )

    class Fake(_SlideshowDaemonMixin):
        def __init__(self):
            self._daemon_active_monitor_id = None
            self._inapp_active_monitor_id = None
            self._current_monitor_id = "0"
            self.monitor_slideshow_queues = {"0": ["/new.jpg"]}

    monkeypatch.setattr(
        "gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._slideshow_daemon.MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH",
        path,
    )
    monkeypatch.setattr(
        "backend.src.utils.display.monitor_slideshow_daemon.daemon_is_live",
        lambda cfg: True,
    )
    # pyrefly: ignore [bad-argument-type]
    Fake()._start_daemon_slideshow("0")
    saved = json.loads(path.read_text())
    assert saved["queue"] == ["/locked.jpg"]
