"""Tests for ScanMetadataTab mixin-to-composition migration (ui-arch-23, #544)."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.classes import AbstractClassTwoGalleries
from gui.src.tabs.database.scan_metadata_tab import ScanMetadataTab
from gui.src.tabs.database.scan_metadata_tab._config import ScanConfigController
from gui.src.tabs.database.scan_metadata_tab._scan_loading import ScanLoadingController
from gui.src.tabs.database.scan_metadata_tab._selection_gallery import ScanSelectionController
from gui.src.tabs.database.scan_metadata_tab._ui_builder import ScanUIBuilder

pytestmark = pytest.mark.gui


class TestScanMetadataTabComposition:
    def test_direct_bases_have_no_mixins(self, q_app):
        assert ScanMetadataTab.__bases__ == (AbstractClassTwoGalleries,)
        assert issubclass(ScanMetadataTab, QWidget)

    def test_controllers_are_composed(self, q_app):
        tab = ScanMetadataTab(database_service=MagicMock(db=None))
        assert isinstance(tab.ui_builder, ScanUIBuilder)
        assert tab.ui_builder.tab is tab
        assert isinstance(tab.scan_loading, ScanLoadingController)
        assert isinstance(tab.selection, ScanSelectionController)
        assert isinstance(tab.config_controller, ScanConfigController)
        tab.close()

    def test_toggle_selection_facade(self, q_app, tmp_path):
        tab = ScanMetadataTab(database_service=MagicMock(db=None))
        paths = []
        for i in range(4):
            p = tmp_path / f"img_{i}.png"
            p.write_bytes(b"x")
            paths.append(str(p))
        tab.scan_image_list = paths
        tab.apply_scan_filters()
        tab.toggle_selection(paths[1])
        assert paths[1] in tab.selected_image_paths
        tab.close()
