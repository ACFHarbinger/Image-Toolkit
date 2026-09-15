"""Advanced Search dialog: merged Tags/Genres list (genres are a tag subtype,
the standalone Genres tab was removed -- see the dialog's docstring).
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage

from gui.src.elements.database.dialog.advanced_search_dialog import _AdvancedSearchDialog
from gui.src.helpers.image import _CARD_THUMB_CACHE

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


class TestAdvancedSearchDialogFilters:
    def test_filter_fields_exist_with_clear_buttons(self, q_app):
        dialog = _AdvancedSearchDialog(entries=ENTRIES, entities=ENTITIES)
        assert dialog.ent_filter is not None
        assert dialog.tag_filter is not None
        assert dialog.ent_filter.isClearButtonEnabled()
        assert dialog.tag_filter.isClearButtonEnabled()
        assert "filter" in dialog.ent_filter.placeholderText().lower()
        assert "filter" in dialog.tag_filter.placeholderText().lower()
        assert dialog.inc_ent_filter is dialog.ent_filter
        assert dialog.inc_tag_filter is dialog.tag_filter

    def test_entity_filter_hides_non_matching_items(self, q_app):
        entities = [
            {"id": "e1", "name": "Alice Wonderland"},
            {"id": "e2", "name": "Bob Builder"},
            {"id": "e3", "name": "Charlie Chaplin"},
        ]
        dialog = _AdvancedSearchDialog(entries=ENTRIES, entities=entities)
        assert dialog.inc_ent_list.count() == 3

        # Filter by "bob"
        dialog.ent_filter.setText("bob")
        assert dialog.inc_ent_list.item(0).isHidden() is True   # Alice
        assert dialog.inc_ent_list.item(1).isHidden() is False  # Bob
        assert dialog.inc_ent_list.item(2).isHidden() is True   # Charlie

        # Exclude list also filtered
        assert dialog.exc_ent_list.item(0).isHidden() is True
        assert dialog.exc_ent_list.item(1).isHidden() is False
        assert dialog.exc_ent_list.item(2).isHidden() is True

        # Clear filter
        dialog.ent_filter.setText("")
        for i in range(3):
            assert dialog.inc_ent_list.item(i).isHidden() is False
            assert dialog.exc_ent_list.item(i).isHidden() is False

    def test_tag_filter_hides_non_matching_items(self, q_app):
        dialog = _AdvancedSearchDialog(entries=ENTRIES, entities=ENTITIES)
        # sorted_tags: ["Action", "blue hair", "Comedy", "outdoor"]
        dialog.tag_filter.setText("hair")
        for i in range(dialog.inc_tag_list.count()):
            item = dialog.inc_tag_list.item(i)
            if item.text() == "blue hair":
                assert item.isHidden() is False
            else:
                assert item.isHidden() is True

    def test_checked_state_preserved_when_filtering_and_retrieving_criteria(self, q_app):
        entities = [
            {"id": "e1", "name": "Alice"},
            {"id": "e2", "name": "Bob"},
        ]
        dialog = _AdvancedSearchDialog(entries=ENTRIES, entities=entities)

        # Filter to Alice, check her in Include
        dialog.ent_filter.setText("Alice")
        dialog.inc_ent_list.item(0).setCheckState(Qt.CheckState.Checked)

        # Filter to Bob, check him in Exclude
        dialog.ent_filter.setText("Bob")
        dialog.exc_ent_list.item(1).setCheckState(Qt.CheckState.Checked)

        # Criteria should include Alice and exclude Bob even while Bob filter is active
        crit = dialog.get_criteria()
        assert crit["include_entities"] == ["e1"]
        assert crit["exclude_entities"] == ["e2"]

        # Clear filter - check states are still preserved
        dialog.ent_filter.clear()
        assert dialog.inc_ent_list.item(0).checkState() == Qt.CheckState.Checked
        assert dialog.exc_ent_list.item(1).checkState() == Qt.CheckState.Checked


class TestAdvancedSearchDialogDeferredIcons:
    def test_uncached_icons_deferred_and_not_blocking_init(self, tmp_path, q_app):
        img_path = str(tmp_path / "test_icon.png")
        img = QImage(100, 100, QImage.Format.Format_RGB32)
        img.fill(QColor("red"))
        img.save(img_path)

        _CARD_THUMB_CACHE.pop(img_path, None)
        entities = [{"id": "e1", "name": "TestEntity", "image_path": img_path}]

        dialog = _AdvancedSearchDialog(entries=ENTRIES, entities=entities)
        # Right after __init__, items should be queued in _pending_icon_items
        assert len(dialog._pending_icon_items) == 2  # 1 for inc, 1 for exc

        # Flush pending icons
        dialog.flush_pending_icons()
        assert len(dialog._pending_icon_items) == 0

        # Now both items should have icons set
        inc_item = dialog.inc_ent_list.item(0)
        exc_item = dialog.exc_ent_list.item(0)
        assert not inc_item.icon().isNull()
        assert not exc_item.icon().isNull()

        # Cache should now be populated
        assert img_path in _CARD_THUMB_CACHE

    def test_cached_icons_applied_immediately(self, tmp_path, q_app):
        img_path = str(tmp_path / "cached_icon.png")
        img = QImage(40, 40, QImage.Format.Format_RGB32)
        img.fill(QColor("blue"))
        _CARD_THUMB_CACHE[img_path] = img

        entities = [{"id": "e1", "name": "CachedEntity", "image_path": img_path}]
        dialog = _AdvancedSearchDialog(entries=ENTRIES, entities=entities)

        # Since it was already cached in memory, zero pending items
        assert len(dialog._pending_icon_items) == 0
        inc_item = dialog.inc_ent_list.item(0)
        assert not inc_item.icon().isNull()

    def test_closing_dialog_cancels_pending_icons(self, tmp_path, q_app):
        img_path = str(tmp_path / "cancel_icon.png")
        entities = [{"id": "e1", "name": "CancelEntity", "image_path": img_path}]

        dialog = _AdvancedSearchDialog(entries=ENTRIES, entities=entities)
        assert len(dialog._pending_icon_items) == 2
        dialog.reject()
        assert dialog._is_closed is True
        assert len(dialog._pending_icon_items) == 0

    def test_construction_with_many_uncached_entities_is_fast(self, q_app):
        import time
        entities = [
            {"id": f"e{i}", "name": f"Entity {i}", "image_path": f"/tmp/nonexistent_{i}.png"}
            for i in range(500)
        ]
        t0 = time.perf_counter()
        dialog = _AdvancedSearchDialog(entries=ENTRIES, entities=entities)
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.2
        assert len(dialog._pending_icon_items) == 1000
        dialog.reject()

