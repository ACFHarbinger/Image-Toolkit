"""Tests for VideoExtractorSubTab mixin-to-composition migration (ui-arch-23, #544)."""

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.classes import AbstractClassSingleGallery
from gui.src.tabs.core.extractor_tab import ExtractorTab, VideoExtractorSubTab
from gui.src.tabs.core.extractor_tab._cloud_dispatch import ExtractorCloudDispatchController
from gui.src.tabs.core.extractor_tab._config_methods import ExtractorConfigMethodsController
from gui.src.tabs.core.extractor_tab._cuts_logic import ExtractorCutsLogicController
from gui.src.tabs.core.extractor_tab._directory_scanning import ExtractorDirectoryScanningController
from gui.src.tabs.core.extractor_tab._extraction_execution import ExtractorExtractionExecutionController
from gui.src.tabs.core.extractor_tab._extraction_panel_ui import ExtractorExtractionPanelUIController
from gui.src.tabs.core.extractor_tab._extraction_workers import ExtractorExtractionWorkersController
from gui.src.tabs.core.extractor_tab._gallery_selection import ExtractorGallerySelectionController
from gui.src.tabs.core.extractor_tab._media_player import ExtractorMediaPlayerController
from gui.src.tabs.core.extractor_tab._player_lifecycle import ExtractorPlayerLifecycleController
from gui.src.tabs.core.extractor_tab._qml_handlers import ExtractorQmlHandlersController
from gui.src.tabs.core.extractor_tab._queue_management import ExtractorQueueManagementController
from gui.src.tabs.core.extractor_tab._tags_logic import ExtractorTagsLogicController
from gui.src.tabs.core.extractor_tab._video_session_history import ExtractorVideoSessionHistoryController
from gui.src.tabs.core.extractor_tab._view_controls import ExtractorViewControlsController
from gui.src.tabs.core.image_extractor_subtab import ImageExtractorSubTab

pytestmark = pytest.mark.gui


class TestVideoExtractorSubTabComposition:
    def test_direct_bases_have_no_mixins(self, q_app):
        assert VideoExtractorSubTab.__bases__ == (AbstractClassSingleGallery,)
        for cls in VideoExtractorSubTab.__bases__:
            assert not cls.__name__.endswith("Mixin")
        assert issubclass(VideoExtractorSubTab, QWidget)

    def test_controllers_are_composed(self, q_app):
        tab = VideoExtractorSubTab()
        assert isinstance(tab.player_lifecycle, ExtractorPlayerLifecycleController)
        assert isinstance(tab.media, ExtractorMediaPlayerController)
        assert tab.media.tab is tab
        assert isinstance(tab.directory, ExtractorDirectoryScanningController)
        assert isinstance(tab.session, ExtractorVideoSessionHistoryController)
        assert isinstance(tab.view_controls, ExtractorViewControlsController)
        assert isinstance(tab.gallery_selection, ExtractorGallerySelectionController)
        assert isinstance(tab.cuts, ExtractorCutsLogicController)
        assert isinstance(tab.tags, ExtractorTagsLogicController)
        assert isinstance(tab.extraction, ExtractorExtractionExecutionController)
        assert isinstance(tab.workers, ExtractorExtractionWorkersController)
        assert isinstance(tab.cloud, ExtractorCloudDispatchController)
        assert isinstance(tab.panel_ui, ExtractorExtractionPanelUIController)
        assert isinstance(tab.queue, ExtractorQueueManagementController)
        assert isinstance(tab.config_controller, ExtractorConfigMethodsController)
        assert isinstance(tab.qml, ExtractorQmlHandlersController)
        tab.close()

    def test_outer_extractor_tab_still_wraps_subtabs(self, q_app):
        tab = ExtractorTab()
        assert type(tab) is ExtractorTab
        assert ExtractorTab.__bases__ == (QWidget,)
        assert isinstance(tab, QWidget)
        assert isinstance(tab.video_subtab, VideoExtractorSubTab)
        assert isinstance(tab.image_subtab, ImageExtractorSubTab)
        tab.close()
