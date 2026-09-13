"""ui-arch-23/#544: MonitorDisplaySubTab composes controllers; WallpaperCommonBase init still runs."""

from __future__ import annotations

import pytest

from gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base import WallpaperCommonBase
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab import MonitorDisplaySubTab
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._lifecycle import (
    MonitorDisplayLifecycleController,
)

pytestmark = pytest.mark.gui


def test_lifecycle_controller_is_constructed(q_app, monkeypatch):
    calls: list[str] = []
    orig = MonitorDisplayLifecycleController.__init__

    def _recording_init(self, tab):
        calls.append("lifecycle")
        orig(self, tab)

    monkeypatch.setattr(MonitorDisplayLifecycleController, "__init__", _recording_init)
    tab = MonitorDisplaySubTab()
    try:
        assert calls == ["lifecycle"]
        assert isinstance(tab.lifecycle_controller, MonitorDisplayLifecycleController)
        assert tab.lifecycle_controller.tab is tab
        assert MonitorDisplaySubTab.__bases__ == (WallpaperCommonBase,)
    finally:
        tab.close()
