"""Composition tests for Wallpaper System/Monitor display subtabs (ui-arch-23, #544)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject

from gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base import (
    WallpaperCommonBase,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab import MonitorDisplaySubTab
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._end_behavior import (
    MonitorDisplayEndBehaviorController,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._graph_ops import (
    MonitorDisplayGraphOpsController,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._lifecycle import (
    MonitorDisplayLifecycleController,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._monitor_management import (
    MonitorDisplayMonitorManagementController,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._preview import (
    MonitorDisplayPreviewController,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._props_behavior import (
    MonitorDisplayPropsBehaviorController,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._sequence_export import (
    MonitorDisplaySequenceExportController,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._serialization import (
    MonitorDisplaySerializationController,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._slideshow_daemon import (
    MonitorDisplaySlideshowDaemonController,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._slideshow_inapp import (
    MonitorDisplaySlideshowInAppController,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._slideshow_status import (
    MonitorDisplaySlideshowStatusController,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._tab_bound import (
    TabBoundController as MonitorTabBoundController,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._ui_graph_canvas import (
    MonitorDisplayUIGraphCanvas,
)
from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab._ui_props_end import (
    MonitorDisplayUIPropsEnd,
)
from gui.src.tabs.core.wallpaper_tab.system_display_subtab import SystemDisplaySubTab
from gui.src.tabs.core.wallpaper_tab.system_display_subtab._config import (
    SystemDisplayConfigController,
)
from gui.src.tabs.core.wallpaper_tab.system_display_subtab._daemon import (
    SystemDisplayDaemonController,
)
from gui.src.tabs.core.wallpaper_tab.system_display_subtab._lifecycle import (
    SystemDisplayLifecycleController,
)
from gui.src.tabs.core.wallpaper_tab.system_display_subtab._slideshow import (
    SystemDisplaySlideshowController,
)
from gui.src.tabs.core.wallpaper_tab.system_display_subtab._style_selectors import (
    SystemDisplayStyleSelectorsController,
)
from gui.src.tabs.core.wallpaper_tab.system_display_subtab._tab_bound import (
    TabBoundController as SystemTabBoundController,
)
from gui.src.tabs.core.wallpaper_tab.system_display_subtab._ui_builder import (
    SystemDisplayUIBuilder,
)
from gui.src.tabs.core.wallpaper_tab.system_display_subtab._wallpaper_worker import (
    SystemDisplayWallpaperWorkerController,
    _WallpaperWorkerCompletionRelay,
)

pytestmark = pytest.mark.gui


class TestWallpaperComposition:
    def test_system_display_bases(self):
        assert SystemDisplaySubTab.__bases__ == (WallpaperCommonBase,)

    def test_monitor_display_bases(self):
        assert MonitorDisplaySubTab.__bases__ == (WallpaperCommonBase,)

    def test_system_display_controllers_composed(self, q_app):
        tab = SystemDisplaySubTab(database_service=SimpleNamespace(db=None))
        try:
            expected = {
                "ui_builder": SystemDisplayUIBuilder,
                "daemon_controller": SystemDisplayDaemonController,
                "style_selectors_controller": SystemDisplayStyleSelectorsController,
                "slideshow_controller": SystemDisplaySlideshowController,
                "lifecycle_controller": SystemDisplayLifecycleController,
                "wallpaper_worker_controller": SystemDisplayWallpaperWorkerController,
                "config_controller": SystemDisplayConfigController,
            }
            for attr, cls in expected.items():
                controller = getattr(tab, attr)
                assert isinstance(controller, cls)
                assert isinstance(controller, SystemTabBoundController)
                assert controller.tab is tab
        finally:
            tab.close()

    def test_monitor_display_controllers_composed(self, q_app):
        tab = MonitorDisplaySubTab()
        try:
            expected = {
                "ui_graph_canvas": MonitorDisplayUIGraphCanvas,
                "ui_props_end": MonitorDisplayUIPropsEnd,
                "monitor_management_controller": MonitorDisplayMonitorManagementController,
                "graph_ops_controller": MonitorDisplayGraphOpsController,
                "props_behavior_controller": MonitorDisplayPropsBehaviorController,
                "end_behavior_controller": MonitorDisplayEndBehaviorController,
                "sequence_export_controller": MonitorDisplaySequenceExportController,
                "slideshow_inapp_controller": MonitorDisplaySlideshowInAppController,
                "slideshow_daemon_controller": MonitorDisplaySlideshowDaemonController,
                "slideshow_status_controller": MonitorDisplaySlideshowStatusController,
                "preview_controller": MonitorDisplayPreviewController,
                "serialization_controller": MonitorDisplaySerializationController,
                "lifecycle_controller": MonitorDisplayLifecycleController,
            }
            for attr, cls in expected.items():
                controller = getattr(tab, attr)
                assert isinstance(controller, cls)
                assert isinstance(controller, MonitorTabBoundController)
                assert controller.tab is tab
        finally:
            tab.close()

    def test_wallpaper_worker_relay_remains_qobject(self):
        assert issubclass(_WallpaperWorkerCompletionRelay, QObject)
        assert not issubclass(_WallpaperWorkerCompletionRelay, SystemTabBoundController)
