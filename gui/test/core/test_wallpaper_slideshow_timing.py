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
