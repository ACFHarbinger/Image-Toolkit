"""System-display daemon: startup liveness reconciliation for a stale running flag."""

from __future__ import annotations

import json
import os

import pytest

pytestmark = pytest.mark.gui


class TestReconcileDaemonLivenessOnStartup:
    def test_stale_running_flag_is_corrected(self, q_app, tmp_path, monkeypatch):
        """A 'running': true flag with a dead pid is stale (ungraceful shutdown
        never reached the daemon's finally cleanup) and must be corrected on
        disk so the UI does not show a dead daemon with a stuck timer."""
        from gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon import (
            _DaemonMixin,
        )

        path = tmp_path / ".slideshow_config.json"
        path.write_text(json.dumps({"running": True, "interval_seconds": 30}))

        pid_path = tmp_path / ".slideshow_daemon.pid"
        pid_path.write_text(str(2**22))

        monkeypatch.setattr(
            "gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon.DAEMON_CONFIG_PATH",
            path,
        )
        monkeypatch.setattr(
            "gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon.PID_PATH",
            pid_path,
        )

        class Fake(_DaemonMixin):
            pass

        tab = Fake()
        # pyrefly: ignore [bad-argument-type]
        assert tab._reconcile_daemon_liveness_on_startup() is False
        assert json.loads(path.read_text())["running"] is False

    def test_live_pid_keeps_running_flag(self, q_app, tmp_path, monkeypatch):
        """A 'running': true flag backed by a genuinely live pid (inherited
        from a previous app session) must stay untouched on disk."""
        from gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon import (
            _DaemonMixin,
        )

        path = tmp_path / ".slideshow_config.json"
        path.write_text(json.dumps({"running": True, "interval_seconds": 30}))

        pid_path = tmp_path / ".slideshow_daemon.pid"
        pid_path.write_text(str(os.getpid()))

        monkeypatch.setattr(
            "gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon.DAEMON_CONFIG_PATH",
            path,
        )
        monkeypatch.setattr(
            "gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon.PID_PATH",
            pid_path,
        )

        class Fake(_DaemonMixin):
            pass

        tab = Fake()
        # pyrefly: ignore [bad-argument-type]
        assert tab._reconcile_daemon_liveness_on_startup() is True
        assert json.loads(path.read_text())["running"] is True

    def test_not_running_is_untouched(self, q_app, tmp_path, monkeypatch):
        """A 'running': false config returns False without any pid check and
        leaves the config file byte-for-byte unchanged."""
        from gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon import (
            _DaemonMixin,
        )

        path = tmp_path / ".slideshow_config.json"
        original = json.dumps({"running": False, "interval_seconds": 30})
        path.write_text(original)

        pid_path = tmp_path / ".slideshow_daemon.pid"
        pid_path.write_text(str(os.getpid()))

        monkeypatch.setattr(
            "gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon.DAEMON_CONFIG_PATH",
            path,
        )
        monkeypatch.setattr(
            "gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon.PID_PATH",
            pid_path,
        )

        class Fake(_DaemonMixin):
            pass

        tab = Fake()
        # pyrefly: ignore [bad-argument-type]
        assert tab._reconcile_daemon_liveness_on_startup() is False
        assert path.read_text() == original
