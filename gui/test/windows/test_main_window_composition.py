"""MainWindow composition of non-Qt mixins (ui-arch-23, #544, F22)."""

from __future__ import annotations

import contextlib

import pytest
from gui.src.windows.main._global_search import MainGlobalSearchController
from gui.src.windows.main._header_builder import MainHeaderBuilderController
from gui.src.windows.main._lifecycle import _LifecycleMixin
from gui.src.windows.main._load_tab_config import MainLoadTabConfigController
from gui.src.windows.main._runtime_shell import MainRuntimeShellController
from gui.src.windows.main._save_tab_config import MainSaveTabConfigController
from gui.src.windows.main._session_recovery import MainSessionRecoveryController
from gui.src.windows.main._shortcuts import MainShortcutOverlayController
from gui.src.windows.main._startup_prefs import MainStartupPrefsController
from gui.src.windows.main._tab_registry import MainTabRegistryController
from gui.src.windows.main._tab_search import MainTabSearchController
from gui.src.windows.main._theme import MainThemeController
from gui.src.windows.main._tray import MainTrayController
from gui.src.windows.main._window_bound import WindowBoundController
from gui.src.windows.main._workflow_templates import MainWorkflowTemplatesController
from gui.src.windows.main._zoom import _ZoomMixin
from gui.src.windows.main.main_window import MainWindow
from gui.test.fixtures.mock_vault_manager import MockVaultManager, cleanup_recovery_files
from PySide6.QtWidgets import QWidget

pytestmark = pytest.mark.gui


class TestMainWindowMro:
    def test_bases_keep_only_qt_override_mixins(self):
        assert MainWindow.__bases__ == (_LifecycleMixin, _ZoomMixin, QWidget)
        extra = [
            cls.__name__
            for cls in MainWindow.__bases__
            if cls.__name__.endswith("Mixin") and cls not in (_LifecycleMixin, _ZoomMixin)
        ]
        assert extra == []


class TestMainWindowControllers:
    @pytest.fixture(autouse=True)
    def _cleanup(self):
        cleanup_recovery_files()
        yield
        cleanup_recovery_files()

    def test_controllers_composed(self, q_app):
        window = MainWindow(vault_manager=MockVaultManager({"account_name": "test_user"}))
        expected = {
            "header_builder": MainHeaderBuilderController,
            "runtime_shell": MainRuntimeShellController,
            "tab_registry": MainTabRegistryController,
            "theme_controller": MainThemeController,
            "tray_controller": MainTrayController,
            "tab_search": MainTabSearchController,
            "global_search": MainGlobalSearchController,
            "workflow_templates": MainWorkflowTemplatesController,
            "shortcut_overlay": MainShortcutOverlayController,
            "save_tab_config": MainSaveTabConfigController,
            "load_tab_config": MainLoadTabConfigController,
            "startup_prefs": MainStartupPrefsController,
            "session_recovery": MainSessionRecoveryController,
        }
        for attr, cls in expected.items():
            controller = getattr(window, attr)
            assert isinstance(controller, cls)
            assert isinstance(controller, WindowBoundController)
            assert controller.tab is window
        with contextlib.suppress(RuntimeError):
            window.close()
            window.deleteLater()
