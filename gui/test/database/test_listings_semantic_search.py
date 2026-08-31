"""DB.7 (listings side): "Search by Meaning" state wiring for
SeriesListingsSubTab/EntityListingsSubTab -- construction smoke test and
the semantic-results precedence branch in _filtered_entries()/
_filtered_entities() (mirrors the existing recommendation-mode branch).
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from gui.src.classes import AbstractClassTwoGalleries
from gui.src.tabs.database.entity_listings_subtab import EntityListingsSubTab
from gui.src.tabs.database.series_listings_subtab import SeriesListingsSubTab

pytestmark = pytest.mark.gui


class TestSeriesListingsSemanticSearch:
    def test_construction(self, q_app):
        tab = SeriesListingsSubTab(vault_manager=None)
        assert isinstance(tab, AbstractClassTwoGalleries)
        assert tab._scroll_zoom_connected
        assert tab._semantic_search_results is None
        assert tab.clear_semantic_btn.isHidden()

    def test_filtered_entries_semantic_mode_ranks_by_score(self, q_app):
        tab = SeriesListingsSubTab(vault_manager=None)
        tab._entries = [
            {"id": "m-1", "title": "A"},
            {"id": "m-2", "title": "B"},
            {"id": "m-3", "title": "C"},
        ]
        # Deliberately out of score order and omitting m-3 -- only matched
        # ids should appear, ranked by descending score.
        tab._semantic_search_results = [("m-2", 0.4), ("m-1", 0.9)]

        result = tab._filtered_entries()

        assert [e["id"] for e in result] == ["m-1", "m-2"]

    def test_clear_semantic_search_resets_state(self, q_app):
        tab = SeriesListingsSubTab(vault_manager=None)
        tab._semantic_search_results = [("m-1", 0.9)]
        tab.clear_semantic_btn.show()

        tab._clear_semantic_search()

        assert tab._semantic_search_results is None
        assert tab.clear_semantic_btn.isHidden()

    def test_gallery_is_paginated(self, q_app):
        tab = SeriesListingsSubTab(vault_manager=None)
        tab._entries = [{"id": f"m-{i}", "title": f"Entry {i}"} for i in range(205)]

        tab._rebuild_gallery()
        assert tab._grid.count() == 100
        tab._change_listing_page(2)
        assert tab._grid.count() == 5

    def test_shared_search_operators(self, q_app):
        tab = SeriesListingsSubTab(vault_manager=None)
        tab._entries = [
            {"id": "m-1", "title": "Cowboy Bebop", "tags": "space jazz"},
            {"id": "m-2", "title": "Space Dandy", "tags": "space comedy"},
            {"id": "m-3", "title": "Monster", "tags": "thriller"},
        ]
        tab._search_query = 'space -comedy "cowboy bebop"'

        assert [entry["id"] for entry in tab._filtered_entries()] == ["m-1"]

    def test_keyboard_navigation_activates_focused_card(self, q_app, monkeypatch):
        tab = SeriesListingsSubTab(vault_manager=None)
        tab._entries = [
            {"id": "m-1", "title": "A"},
            {"id": "m-2", "title": "B"},
        ]
        tab._rebuild_gallery()
        activated = []
        monkeypatch.setattr(tab, "_on_card_clicked", activated.append)

        tab.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier))
        tab.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))

        assert activated == ["m-2"]

    def test_ctrl_wheel_zoom_rebuilds_cards_at_new_size(self, q_app, monkeypatch):
        tab = SeriesListingsSubTab(vault_manager=None)
        tab._entries = [{"id": "m-1", "title": "A"}]
        tab._rebuild_gallery()
        old_size = tab._listing_card_size
        monkeypatch.setattr(tab, "_save_thumbnail_size", lambda: None)

        tab._on_listing_zoom(120)

        assert tab._listing_card_size == old_size + 16
        assert tab._listing_card_map["m-1"].width() == old_size + 26

    def test_rerun_recommendation_does_not_terminate_qthread(self, q_app, monkeypatch):
        tab = SeriesListingsSubTab(vault_manager=None)
        old = MagicMock()
        old.isRunning.return_value = True
        tab._active_rec_worker = old
        fake_worker = MagicMock()
        monkeypatch.setattr(
            "gui.src.tabs.database.series_listings_subtab._recommendation.RecommendationWorker",
            lambda *args, **kwargs: fake_worker,
        )
        tab._run_recommendation({"prompt": "x"})
        old.terminate.assert_not_called()
        old.requestInterruption.assert_called_once()
        old.wait.assert_called_once_with()
        fake_worker.start.assert_called_once()


class TestEntityListingsSemanticSearch:
    def test_construction(self, q_app):
        tab = EntityListingsSubTab(vault_manager=None)
        assert isinstance(tab, AbstractClassTwoGalleries)
        assert tab._scroll_zoom_connected
        assert tab._semantic_search_results is None
        assert tab.clear_semantic_btn.isHidden()

    def test_filtered_entities_semantic_mode_ranks_by_score(self, q_app):
        tab = EntityListingsSubTab(vault_manager=None)
        tab._entities = [
            {"id": "e-1", "name": "Alpha"},
            {"id": "e-2", "name": "Beta"},
        ]
        tab._semantic_search_results = [("e-2", 0.2), ("e-1", 0.8)]

        result = tab._filtered_entities()

        assert [e["id"] for e in result] == ["e-1", "e-2"]

    def test_clear_semantic_search_resets_state(self, q_app):
        tab = EntityListingsSubTab(vault_manager=None)
        tab._semantic_search_results = [("e-1", 0.9)]
        tab.clear_semantic_btn.show()

        tab._clear_semantic_search()

        assert tab._semantic_search_results is None
        assert tab.clear_semantic_btn.isHidden()

    def test_gallery_is_paginated(self, q_app):
        tab = EntityListingsSubTab(vault_manager=None)
        tab._entities = [{"id": f"e-{i}", "name": f"Entity {i}"} for i in range(205)]

        tab._rebuild_gallery()
        assert tab._grid.count() == 100
        tab._change_listing_page(2)
        assert tab._grid.count() == 5

    def test_shared_or_and_exclude_search_operators(self, q_app):
        tab = EntityListingsSubTab(vault_manager=None)
        tab._entities = [
            {"id": "e-1", "name": "Spike Spiegel", "role": "Protagonist"},
            {"id": "e-2", "name": "Vicious", "role": "Antagonist"},
            {"id": "e-3", "name": "Faye Valentine", "role": "Protagonist"},
        ]
        tab._search_query = "spike|faye -valentine"

        assert [entity["id"] for entity in tab._filtered_entities()] == ["e-1"]

    def test_color_label_changes_card_border(self, q_app, monkeypatch):
        from gui.src.windows.settings.app_settings import AppSettings

        tab = EntityListingsSubTab(vault_manager=None)
        tab._entities = [{"id": "e-1", "name": "Spike"}]
        monkeypatch.setattr(AppSettings, "label", lambda _key: "blue")
        tab._rebuild_gallery()

        assert "#3498db" in tab._listing_card_map["e-1"].styleSheet()
