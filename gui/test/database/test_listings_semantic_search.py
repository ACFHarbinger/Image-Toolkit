"""DB.7 (listings side): "Search by Meaning" state wiring for
SeriesListingsSubTab/EntityListingsSubTab -- construction smoke test and
the semantic-results precedence branch in _filtered_entries()/
_filtered_entities() (mirrors the existing recommendation-mode branch).
"""

import pytest
from gui.src.tabs.database.entity_listings_subtab import EntityListingsSubTab
from gui.src.tabs.database.series_listings_subtab import SeriesListingsSubTab

pytestmark = pytest.mark.gui


class TestSeriesListingsSemanticSearch:
    def test_construction(self, q_app):
        tab = SeriesListingsSubTab(vault_manager=None)
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


class TestEntityListingsSemanticSearch:
    def test_construction(self, q_app):
        tab = EntityListingsSubTab(vault_manager=None)
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
