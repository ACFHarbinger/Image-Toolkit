"""Tests for DriveSyncTab mixin-to-composition migration (ui-arch-23, #544)."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.tabs.web.drive_sync_tab import DriveSyncTab
from gui.src.tabs.web.drive_sync_tab._auth_config import DriveSyncAuthController
from gui.src.tabs.web.drive_sync_tab._browsers import DriveSyncBrowsersController
from gui.src.tabs.web.drive_sync_tab._config import DriveSyncConfigController
from gui.src.tabs.web.drive_sync_tab._defaults import DriveSyncDefaultsController
from gui.src.tabs.web.drive_sync_tab._provider_switch import DriveSyncProviderController
from gui.src.tabs.web.drive_sync_tab._remote_map import DriveSyncRemoteMapController
from gui.src.tabs.web.drive_sync_tab._share_folder import DriveSyncShareFolderController
from gui.src.tabs.web.drive_sync_tab._sync_worker import DriveSyncSyncWorkerController
from gui.src.tabs.web.drive_sync_tab._ui_builder import DriveSyncUIBuilder
from gui.src.tabs.web.drive_sync_tab._ui_lock import DriveSyncUILockController

pytestmark = pytest.mark.gui


class TestDriveSyncComposition:
    def test_drive_sync_tab_direct_bases_have_no_mixins(self, q_app):
        bases = DriveSyncTab.__bases__
        assert bases == (QWidget,)
        for cls in bases:
            assert not cls.__name__.endswith("Mixin")
        assert issubclass(DriveSyncTab, QWidget)

    def test_controllers_are_composed(self, q_app):
        mock_vault = MagicMock()
        mock_vault.api_credentials = {}
        tab = DriveSyncTab(mock_vault)
        assert isinstance(tab.ui_builder, DriveSyncUIBuilder)
        assert tab.ui_builder.tab is tab
        assert isinstance(tab.provider_controller, DriveSyncProviderController)
        assert tab.provider_controller.tab is tab
        assert isinstance(tab.auth_controller, DriveSyncAuthController)
        assert tab.auth_controller.tab is tab
        assert isinstance(tab.defaults_controller, DriveSyncDefaultsController)
        assert tab.defaults_controller.tab is tab
        assert isinstance(tab.remote_map_controller, DriveSyncRemoteMapController)
        assert tab.remote_map_controller.tab is tab
        assert isinstance(tab.share_folder_controller, DriveSyncShareFolderController)
        assert tab.share_folder_controller.tab is tab
        assert isinstance(tab.sync_worker_controller, DriveSyncSyncWorkerController)
        assert tab.sync_worker_controller.tab is tab
        assert isinstance(tab.ui_lock_controller, DriveSyncUILockController)
        assert tab.ui_lock_controller.tab is tab
        assert isinstance(tab.browsers_controller, DriveSyncBrowsersController)
        assert tab.browsers_controller.tab is tab
        assert isinstance(tab.config_controller, DriveSyncConfigController)
        assert tab.config_controller.tab is tab
        tab.close()

    def test_tab_bound_controller_attribute_proxy(self, q_app):
        mock_vault = MagicMock()
        mock_vault.api_credentials = {}
        tab = DriveSyncTab(mock_vault)
        tab.custom_test_val = "hello_proxy"
        assert tab.config_controller.custom_test_val == "hello_proxy"
        tab.close()

    def test_facade_delegates_collect_and_default_config(self, q_app):
        mock_vault = MagicMock()
        mock_vault.api_credentials = {}
        tab = DriveSyncTab(mock_vault)
        cfg = tab.collect()
        assert "provider" in cfg
        assert "sync_data" in cfg
        assert "local_dir_sync" in cfg

        def_cfg = tab.get_default_config()
        assert "provider" in def_cfg
        assert def_cfg["dry_run"] is True
        tab.close()
