"""Wallpaper slideshow timing: transition delay setting (and the reset-timer button)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from gui.src.tabs.core.wallpaper_tab import WallpaperTab

pytestmark = pytest.mark.gui

_SD = "gui.src.tabs.core.wallpaper_tab.system_display_subtab"


@pytest.fixture
def wallpaper_tab(q_app, tmp_path, monkeypatch):
    from screeninfo import Monitor

    monitor = Monitor(name="Display1", x=0, y=0, width=1920, height=1080, is_primary=True)
    config_path = tmp_path / ".slideshow_config.json"
    for mod in ("_daemon", "_slideshow"):
        monkeypatch.setattr(f"{_SD}.{mod}.DAEMON_CONFIG_PATH", config_path)
    with (
        patch(f"{_SD}._wallpaper_worker.WallpaperWorker"),
        patch(
            "gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base._monitor_layout.get_monitors",
            return_value=[monitor],
        ),
    ):
        tab = WallpaperTab(db_tab_ref=MagicMock())
        tab.daemon_config_path = config_path
        yield tab
        tab.close()


def test_transition_delay_defaults_to_three_and_persists(wallpaper_tab):
    sd = wallpaper_tab.system_display
    assert sd.transition_delay_spinbox.value() == 3
    assert sd.get_default_config()["transition_delay_seconds"] == 3

    sd.transition_delay_spinbox.setValue(5)
    assert sd.collect()["transition_delay_seconds"] == 5
    sd.set_config({"transition_delay_seconds": 0})
    assert sd.transition_delay_spinbox.value() == 0
    sd.set_config({"transition_delay_seconds": "bad"})
    assert sd.transition_delay_spinbox.value() == 3


def test_in_app_period_adds_the_delay(wallpaper_tab):
    sd = wallpaper_tab.system_display
    sd.interval_sec = 90
    assert sd.slideshow_controller._slideshow_period_sec() == 93
    sd.transition_delay_spinbox.setValue(0)
    assert sd.slideshow_controller._slideshow_period_sec() == 90


def test_daemon_config_carries_delay_separately(wallpaper_tab):
    sd = wallpaper_tab.system_display
    sd.interval_min_spinbox.setValue(1)
    sd.interval_sec_spinbox.setValue(30)
    sd.transition_delay_spinbox.setValue(4)
    sd.daemon_controller.toggle_daemon(False)
    written = json.loads(wallpaper_tab.daemon_config_path.read_text())
    assert written["interval_seconds"] == 90
    assert written["transition_delay_seconds"] == 4


def test_monitor_display_uses_the_shared_delay(wallpaper_tab):
    from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._slideshow_inapp import transition_delay_for

    wallpaper_tab.system_display.transition_delay_spinbox.setValue(6)
    assert transition_delay_for(wallpaper_tab.monitor_display) == 6
    assert transition_delay_for(object()) == 3


# --- Reset Timer --------------------------------------------------------------


def test_reset_button_restarts_local_slideshow_countdown(wallpaper_tab):
    from PySide6.QtCore import QTimer

    sd = wallpaper_tab.system_display
    sd.interval_sec = 90
    timer = QTimer(sd)
    timer.start(93_000)
    sd.slideshow_timer = timer
    sd.time_remaining_sec = 12

    sd.btn_reset_timer.click()
    assert sd.time_remaining_sec == 93
    assert sd.countdown_label.text() == "Timer: 01:33"
    assert timer.isActive() and timer.remainingTime() > 92_000
    timer.stop()


def test_reset_button_signals_the_daemon(wallpaper_tab):
    sd = wallpaper_tab.system_display
    path = wallpaper_tab.daemon_config_path
    path.write_text(json.dumps({"running": True, "interval_seconds": 90, "transition_delay_seconds": 3,
                                "last_change_timestamp": 1}))
    sd.time_remaining_sec = 5

    sd.btn_reset_timer.click()
    written = json.loads(path.read_text())
    assert isinstance(written["timer_reset_token"], int)
    assert written["last_change_timestamp"] > 1
    assert written["interval_seconds"] == 90
    assert sd.time_remaining_sec == 93

    first = written["timer_reset_token"]
    sd.btn_reset_timer.click()
    assert json.loads(path.read_text())["timer_reset_token"] != first


def test_reset_button_is_a_noop_without_a_slideshow(wallpaper_tab):
    sd = wallpaper_tab.system_display
    sd.time_remaining_sec = 7
    sd.btn_reset_timer.click()
    assert sd.time_remaining_sec == 7
    assert not wallpaper_tab.daemon_config_path.exists()


def test_monitor_display_reset_restarts_scheduler_in_place(wallpaper_tab, monkeypatch):
    md = wallpaper_tab.monitor_display
    inapp = "gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._slideshow_inapp._monitor_slideshow"
    native = MagicMock()
    native.status.return_value = {"running": True, "current_index": 1}
    monkeypatch.setattr(inapp, native)
    monkeypatch.setattr(
        "gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._slideshow_status._monitor_slideshow", native
    )
    mid = md._current_monitor_id
    assert mid is not None
    md.monitor_slideshow_queues[mid] = ["/a.png", "/b.png", "/c.png"]
    md._reconcile_queue_durations = lambda _mid: [10, 10, 10]

    assert not md._btn_reset_slideshow_timer.isEnabled()
    md._inapp_active_monitor_id = mid
    md._update_slideshow_buttons()
    assert md._btn_reset_slideshow_timer.isEnabled()

    md._btn_reset_slideshow_timer.click()
    native.stop.assert_called()
    kwargs = native.start.call_args.kwargs
    assert kwargs["start_index"] == 1
    assert kwargs["skip_first_apply"] is True
    assert kwargs["transition_delay"] == 3
    assert md._inapp_active_monitor_id == mid


def test_monitor_display_reset_signals_its_daemon(wallpaper_tab, tmp_path, monkeypatch):
    md = wallpaper_tab.monitor_display
    cfg_path = tmp_path / "monitor_daemon.json"
    cfg_path.write_text(json.dumps({"running": True, "monitor_id": "x", "pid": 1}))
    monkeypatch.setattr(
        "gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._slideshow_daemon.MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH",
        cfg_path,
    )
    monkeypatch.setattr(
        "gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._slideshow_daemon._monitor_slideshow.daemon_is_live",
        lambda cfg: bool(cfg and cfg.get("running")),
    )
    md._daemon_active_monitor_id = md._current_monitor_id
    md._btn_reset_slideshow_timer.setEnabled(True)
    md._btn_reset_slideshow_timer.click()
    assert isinstance(json.loads(cfg_path.read_text())["timer_reset_token"], int)
