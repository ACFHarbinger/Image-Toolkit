"""Tests for MediaLoaderTab mixin-to-composition migration (ui-arch-23, #544)."""

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.tabs.web.media_loader_tab import MediaLoaderTab
from gui.src.tabs.web.media_loader_tab._directory_browse import MediaLoaderDirectoryController
from gui.src.tabs.web.media_loader_tab._download_worker import MediaLoaderWorkerController
from gui.src.tabs.web.media_loader_tab._source_switch import MediaLoaderSourceController
from gui.src.tabs.web.media_loader_tab._ui_builder import MediaLoaderUIBuilder

pytestmark = pytest.mark.gui


class TestMediaLoaderComposition:
    def test_media_loader_tab_direct_bases_have_no_mixins(self, q_app):
        bases = MediaLoaderTab.__bases__
        assert bases == (QWidget,)
        for cls in bases:
            assert not cls.__name__.endswith("Mixin")
        assert issubclass(MediaLoaderTab, QWidget)

    def test_controllers_are_composed(self, q_app):
        tab = MediaLoaderTab()
        assert isinstance(tab.ui_builder, MediaLoaderUIBuilder)
        assert tab.ui_builder.tab is tab
        assert isinstance(tab.source_controller, MediaLoaderSourceController)
        assert tab.source_controller.tab is tab
        assert isinstance(tab.directory_controller, MediaLoaderDirectoryController)
        assert tab.directory_controller.tab is tab
        assert isinstance(tab.worker_controller, MediaLoaderWorkerController)
        assert tab.worker_controller.tab is tab
        tab.close()

    def test_tab_bound_controller_attribute_proxy(self, q_app):
        tab = MediaLoaderTab()
        tab.custom_proxy_test = "media_loader_val"
        assert tab.directory_controller.custom_proxy_test == "media_loader_val"
        tab.close()
