"""Tests for SimilarityTab mixin-to-composition migration (ui-arch-23, #544)."""

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.classes import AbstractClassTwoGalleries
from gui.src.tabs.core.similarity_tab import SimilarityTab
from gui.src.tabs.core.similarity_tab._config import SimilarityConfigController
from gui.src.tabs.core.similarity_tab._deletion import SimilarityDeletionController
from gui.src.tabs.core.similarity_tab._triage_selection import SimilarityTriageSelectionController
from gui.src.tabs.core.similarity_tab._ui_builder import SimilarityUIBuilder

pytestmark = pytest.mark.gui


class TestSimilarityTabComposition:
    def test_direct_bases_have_no_mixins(self, q_app):
        assert SimilarityTab.__bases__ == (AbstractClassTwoGalleries,)
        assert issubclass(SimilarityTab, QWidget)

    def test_controllers_are_composed(self, q_app):
        tab = SimilarityTab()
        assert isinstance(tab.ui_builder, SimilarityUIBuilder)
        assert tab.ui_builder.tab is tab
        assert isinstance(tab.triage, SimilarityTriageSelectionController)
        assert tab.triage.tab is tab
        assert isinstance(tab.deletion, SimilarityDeletionController)
        assert isinstance(tab.config_controller, SimilarityConfigController)
        tab.close()

    def test_toggle_selection_facade(self, q_app, tmp_path):
        tab = SimilarityTab()
        paths = []
        for i in range(4):
            p = tmp_path / f"img_{i}.png"
            p.write_bytes(b"x")
            paths.append(str(p))
        tab.start_loading_thumbnails(paths)
        tab.toggle_selection(paths[1])
        assert paths[1] in tab.selected_files
        tab.close()

    def test_get_default_config_keys(self, q_app):
        tab = SimilarityTab()
        cfg = tab.get_default_config()
        assert set(cfg) >= {
            "target_path",
            "reference_path",
            "recursive",
            "scan_method",
            "target_extensions",
            "require_confirm",
            "similarity",
            "triage",
        }
        tab.close()
