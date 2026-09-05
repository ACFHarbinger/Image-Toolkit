""""Search with this tag" actions (Management -> Search tab), and the
generic ``TagChipEditor`` widget (Genres/Tags fields it used to power on
the listings detail panel were replaced by the grouped-tags "+"
add-tag action -- see test_detail_panel_links.py -- but the widget
itself remains a reusable component).
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt

from gui.src.modules.events import EventHub, FilterByTagIntent, NavigateIntent
from gui.src.tabs.database.database_tab import DatabaseTab
from gui.src.tabs.database.search_tab import SearchTab

pytestmark = pytest.mark.gui


class TestTagChipEditor:
    """issue #127: TagChipEditor replaces the plain CSV QLineEdit for
    Genres/Tags -- setText/text/clear must stay drop-in compatible, and
    chip add/remove must update the underlying tag list correctly."""

    def test_set_text_populates_chips(self, q_app):
        from gui.src.components.tag_chip_widget import TagChipEditor

        editor = TagChipEditor()
        editor.setText("Action, Sci-Fi, Space Cowboy")
        assert editor.text() == "Action, Sci-Fi, Space Cowboy"
        assert editor._flow.count() == 3

    def test_set_text_dedupes_preserving_order(self, q_app):
        from gui.src.components.tag_chip_widget import TagChipEditor

        editor = TagChipEditor()
        editor.setText("Action, Sci-Fi, Action")
        assert editor.text() == "Action, Sci-Fi"

    def test_enter_commits_chip_and_clears_input(self, q_app):
        from gui.src.components.tag_chip_widget import TagChipEditor

        editor = TagChipEditor()
        editor.add_edit.setText("Drama")
        editor.add_edit.returnPressed.emit()
        assert editor.text() == "Drama"
        assert editor.add_edit.text() == ""

    def test_removing_a_chip_updates_text(self, q_app):
        from gui.src.components.tag_chip_widget import TagChipEditor

        editor = TagChipEditor()
        editor.setText("Action, Sci-Fi")
        chip = editor._flow.itemAt(0).widget()
        chip.removed.emit(chip.tag_text)
        assert editor.text() == "Sci-Fi"

    def test_clear_empties_chips_and_input(self, q_app):
        from gui.src.components.tag_chip_widget import TagChipEditor

        editor = TagChipEditor()
        editor.setText("Action, Sci-Fi")
        editor.add_edit.setText("leftover")
        editor.clear()
        assert editor.text() == ""
        assert editor.add_edit.text() == ""

    def test_completion_activated_commits_chip(self, q_app):
        from gui.src.components.tag_chip_widget import TagChipEditor

        editor = TagChipEditor()
        editor.add_edit.setText("Sci")
        editor._on_completion_activated("Sci-Fi")
        assert editor.text() == "Sci-Fi"
        assert editor.add_edit.text() == ""


class TestSearchImagesWithTag:
    def test_no_selection_warns(self, q_app):
        tab = DatabaseTab()
        with patch(
            "gui.src.tabs.database.database_tab._crud.QMessageBox.warning"
        ) as mock_warn:
            tab.search_images_with_selected_tag()
            mock_warn.assert_called_once()

    def test_no_event_hub_warns(self, q_app):
        tab = DatabaseTab()
        tab.tags_table.setRowCount(1)
        from PySide6.QtWidgets import QTableWidgetItem

        tab.tags_table.setItem(0, 0, QTableWidgetItem("sunset"))
        tab.tags_table.setCurrentCell(0, 0)
        with patch(
            "gui.src.tabs.database.database_tab._crud.QMessageBox.warning"
        ) as mock_warn:
            tab.search_images_with_selected_tag()
            mock_warn.assert_called_once()

    def test_dispatches_filter_then_navigation_intents(self, q_app):
        hub = EventHub(q_app)
        tab = DatabaseTab(event_hub=hub)
        from PySide6.QtWidgets import QTableWidgetItem

        tab.tags_table.setRowCount(1)
        tab.tags_table.setItem(0, 0, QTableWidgetItem("sunset"))
        tab.tags_table.setCurrentCell(0, 0)
        received = []
        hub.subscribe(FilterByTagIntent, received.append)
        hub.subscribe(NavigateIntent, received.append)

        with patch(
            "gui.src.tabs.database.database_tab._crud.QMessageBox.information"
        ):
            tab.search_images_with_selected_tag()

        assert [(type(event), event.module_id) for event in received] == [
            (FilterByTagIntent, "library.search"),
            (NavigateIntent, "library.search"),
        ]


class TestSearchListingsWithTag:
    def test_no_selection_warns(self, q_app):
        tab = DatabaseTab()
        with patch(
            "gui.src.tabs.database.database_tab._crud.QMessageBox.warning"
        ) as mock_warn:
            tab.search_listings_with_selected_tag()
            mock_warn.assert_called_once()

    def test_no_event_hub_warns(self, q_app):
        tab = DatabaseTab()
        from PySide6.QtWidgets import QTableWidgetItem

        tab.tags_table.setRowCount(1)
        tab.tags_table.setItem(0, 0, QTableWidgetItem("sunset"))
        tab.tags_table.setCurrentCell(0, 0)
        with patch(
            "gui.src.tabs.database.database_tab._crud.QMessageBox.warning"
        ) as mock_warn:
            tab.search_listings_with_selected_tag()
            mock_warn.assert_called_once()

    def test_dispatches_listings_filter_then_navigation_intents(self, q_app):
        hub = EventHub(q_app)
        tab = DatabaseTab(event_hub=hub)
        from PySide6.QtWidgets import QTableWidgetItem

        tab.tags_table.setRowCount(1)
        tab.tags_table.setItem(0, 0, QTableWidgetItem("sunset"))
        tab.tags_table.setCurrentCell(0, 0)

        received = []
        hub.subscribe(FilterByTagIntent, received.append)
        hub.subscribe(NavigateIntent, received.append)

        tab.search_listings_with_selected_tag()

        assert [(type(event), event.module_id) for event in received] == [
            (FilterByTagIntent, "library.listings"),
            (NavigateIntent, "library.listings"),
        ]

    def test_listings_navigation_uses_hub_without_legacy_window_ref(self, q_app):
        hub = EventHub(q_app)
        tab = DatabaseTab(event_hub=hub)
        from PySide6.QtWidgets import QTableWidgetItem

        tab.tags_table.setRowCount(1)
        tab.tags_table.setItem(0, 0, QTableWidgetItem("sunset"))
        tab.tags_table.setCurrentCell(0, 0)
        received = []
        hub.subscribe(NavigateIntent, received.append)
        tab.search_listings_with_selected_tag()
        assert received[0].module_id == "library.listings"


class TestSearchTabFilterByGroup:
    def test_filter_by_group_checks_only_target_group_and_searches(self, q_app):
        mock_db_tab = MagicMock()
        mock_db_tab.db = MagicMock()
        mock_db_tab.db.get_all_groups.return_value = ["Trips", "Voyages"]
        mock_db_tab.db.get_all_subgroups_detailed.return_value = []
        tab = SearchTab(mock_db_tab)

        with patch(
            "gui.src.tabs.database.search_tab._search_worker.QThreadPool"
        ):
            tab.filter_by_group("Voyages")

        assert tab.get_selected_groups() == ["Voyages"]
        assert tab.filename_edit.text() == ""


class TestSearchTabSearchByTag:
    def test_search_by_tag_checks_type_and_tag_then_searches(self, q_app):
        mock_db_tab = MagicMock()
        mock_db_tab.db = MagicMock()
        mock_db_tab.db.get_all_tags_with_categories.return_value = [
            {"name": "sunset", "category": "General", "color": "#95a5a6"},
            {"name": "portrait", "category": "General", "color": "#95a5a6"},
        ]
        mock_db_tab.db.list_tag_categories.return_value = [
            {"name": "General", "color": "#95a5a6"},
        ]
        tab = SearchTab(mock_db_tab)
        tab._setup_tag_checkboxes()  # populate _all_tags_cache + type list

        with patch(
            "gui.src.tabs.database.search_tab._search_worker.QThreadPool"
        ):
            tab.search_by_tag("sunset")

        # Every tag-type filter checked (so "sunset" wasn't hidden by type).
        for i in range(tab.tag_types_list_widget.count()):
            assert tab.tag_types_list_widget.item(i).checkState() == Qt.CheckState.Checked

        matched = [
            tab.tags_list_widget.item(i)
            for i in range(tab.tags_list_widget.count())
            if tab.tags_list_widget.item(i).data(Qt.ItemDataRole.UserRole) == "sunset"
        ]
        assert len(matched) == 1
        assert matched[0].checkState() == Qt.CheckState.Checked
        assert tab.get_selected_tags() == ["sunset"]
