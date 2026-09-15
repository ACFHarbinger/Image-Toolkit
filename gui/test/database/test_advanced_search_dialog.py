"""Advanced Search dialog: merged Tags/Genres list (genres are a tag subtype,
the standalone Genres tab was removed -- see the dialog's docstring).
"""

from PySide6.QtCore import Qt

from gui.src.elements.database.dialog.advanced_search_dialog import _AdvancedSearchDialog

ENTRIES = [
    {"tags": "blue hair, outdoor", "genres": "Action"},
    {"tags": "blue hair", "genres": "Action, Comedy"},
]
ENTITIES = [{"id": "e1", "name": "Alice", "image_path": ""}]
ENTITIES_AS_ENTRIES = [{"tags": "blue hair"}, {"tags": "blue hair, green hair"}]


class TestAdvancedSearchDialogMergedTags:
    def test_genres_tab_removed(self, q_app):
        dialog = _AdvancedSearchDialog(entries=ENTRIES, entities=ENTITIES)
        titles = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        assert titles == ["👥 Entities", "🏷 Tags"]

    def test_tags_and_genres_merge_into_one_sorted_list(self, q_app):
        dialog = _AdvancedSearchDialog(entries=ENTRIES, entities=ENTITIES)
        assert dialog.sorted_tags == ["Action", "blue hair", "Comedy", "outdoor"]

    def test_get_criteria_buckets_checked_names_by_original_category(self, q_app):
        dialog = _AdvancedSearchDialog(entries=ENTRIES, entities=ENTITIES)
        for idx in range(dialog.inc_tag_list.count()):
            item = dialog.inc_tag_list.item(idx)
            if item.text() in ("Action", "blue hair"):
                item.setCheckState(Qt.CheckState.Checked)

        crit = dialog.get_criteria()

        assert crit["include_tags"] == ["blue hair"]
        assert crit["include_genres"] == ["Action"]

    def test_load_criteria_checks_names_from_either_bucket(self, q_app):
        dialog = _AdvancedSearchDialog(entries=ENTRIES, entities=ENTITIES)
        dialog.load_criteria({"include_genres": ["Comedy"], "include_tags": ["outdoor"]})

        checked = {
            dialog.inc_tag_list.item(i).text()
            for i in range(dialog.inc_tag_list.count())
            if dialog.inc_tag_list.item(i).checkState() == Qt.CheckState.Checked
        }
        assert checked == {"Comedy", "outdoor"}

    def test_entity_mode_relabels_entities_tab_as_associated_entities(self, q_app):
        dialog = _AdvancedSearchDialog(entries=ENTITIES_AS_ENTRIES, entities=ENTITIES, mode="entity")
        titles = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        assert titles == ["👥 Associated Entities", "🏷 Tags"]
        assert dialog.windowTitle() == "🔍 Advanced Entity Search Settings"
