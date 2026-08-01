"""DB.8c: tag-chip autocomplete (listings detail panel) + "search with
this tag" actions (Maintenance -> Search tab).
"""

from unittest.mock import MagicMock, patch

import pytest
from gui.src.tabs.core.elements.display.detail_panel import _DetailPanel
from gui.src.tabs.database.database_tab import DatabaseTab
from gui.src.tabs.database.search_tab import SearchTab
from PySide6.QtCore import Qt

pytestmark = pytest.mark.gui


class TestDetailPanelTagCompleter:
    def test_completers_attached_on_construction(self, q_app):
        panel = _DetailPanel()
        assert panel.f_genres.completer() is panel._genres_completer
        assert panel.f_tags.completer() is panel._tags_completer

    def test_refresh_vocabulary_populates_completers(self, q_app):
        panel = _DetailPanel()
        mock_db = MagicMock()

        with patch(
            "gui.src.tabs.core.elements.display.detail_panel._tag_vocabulary.get_library_db",
            return_value=mock_db,
        ), patch(
            "gui.src.tabs.core.elements.display.detail_panel._tag_vocabulary.TagRepo"
        ) as mock_tag_repo_cls:
            mock_tag_repo_cls.return_value.get_all_tags.return_value = ["Action", "Sci-Fi"]
            panel._refresh_tag_vocabulary()

        assert panel._genres_completer.get_matching_tags("") == ["Action", "Sci-Fi"]
        assert panel._tags_completer.get_matching_tags("") == ["Action", "Sci-Fi"]

    def test_refresh_vocabulary_no_session_is_noop(self, q_app):
        panel = _DetailPanel()
        with patch(
            "gui.src.tabs.core.elements.display.detail_panel._tag_vocabulary.get_library_db",
            return_value=None,
        ):
            panel._refresh_tag_vocabulary()  # must not raise
        assert panel._genres_completer.get_matching_tags("") == []


class TestSearchImagesWithTag:
    def test_no_selection_warns(self, q_app):
        tab = DatabaseTab()
        with patch(
            "gui.src.tabs.database.database_tab._crud.QMessageBox.warning"
        ) as mock_warn:
            tab.search_images_with_selected_tag()
            mock_warn.assert_called_once()

    def test_no_search_tab_ref_warns(self, q_app):
        tab = DatabaseTab()
        tab.tags_table.setRowCount(1)
        from PySide6.QtWidgets import QTableWidgetItem

        tab.tags_table.setItem(0, 0, QTableWidgetItem("sunset"))
        tab.tags_table.setCurrentCell(0, 0)
        tab.search_tab_ref = None

        with patch(
            "gui.src.tabs.database.database_tab._crud.QMessageBox.warning"
        ) as mock_warn:
            tab.search_images_with_selected_tag()
            mock_warn.assert_called_once()

    def test_dispatches_to_search_tab_ref(self, q_app):
        tab = DatabaseTab()
        from PySide6.QtWidgets import QTableWidgetItem

        tab.tags_table.setRowCount(1)
        tab.tags_table.setItem(0, 0, QTableWidgetItem("sunset"))
        tab.tags_table.setCurrentCell(0, 0)
        mock_search_tab = MagicMock()
        tab.search_tab_ref = mock_search_tab

        with patch(
            "gui.src.tabs.database.database_tab._crud.QMessageBox.information"
        ):
            tab.search_images_with_selected_tag()

        mock_search_tab.search_by_tag.assert_called_once_with("sunset")


class TestSearchListingsWithTag:
    def test_no_selection_warns(self, q_app):
        tab = DatabaseTab()
        with patch(
            "gui.src.tabs.database.database_tab._crud.QMessageBox.warning"
        ) as mock_warn:
            tab.search_listings_with_selected_tag()
            mock_warn.assert_called_once()

    def test_no_listings_tab_ref_warns(self, q_app):
        tab = DatabaseTab()
        from PySide6.QtWidgets import QTableWidgetItem

        tab.tags_table.setRowCount(1)
        tab.tags_table.setItem(0, 0, QTableWidgetItem("sunset"))
        tab.tags_table.setCurrentCell(0, 0)
        tab.listings_tab_ref = None

        with patch(
            "gui.src.tabs.database.database_tab._crud.QMessageBox.warning"
        ) as mock_warn:
            tab.search_listings_with_selected_tag()
            mock_warn.assert_called_once()

    def test_dispatches_to_listings_tab_and_switches_main_window(self, q_app):
        tab = DatabaseTab()
        from PySide6.QtWidgets import QTableWidgetItem

        tab.tags_table.setRowCount(1)
        tab.tags_table.setItem(0, 0, QTableWidgetItem("sunset"))
        tab.tags_table.setCurrentCell(0, 0)

        mock_listings_tab = MagicMock()
        tab.listings_tab_ref = mock_listings_tab
        mock_mw = MagicMock()
        tab.main_window_ref = mock_mw

        tab.search_listings_with_selected_tag()

        mock_listings_tab.tab_widget.setCurrentWidget.assert_called_once_with(
            mock_listings_tab.content_listings
        )
        mock_listings_tab.content_listings.search_box.setText.assert_called_once_with(
            "sunset"
        )
        mock_mw.command_combo.setCurrentText.assert_called_once_with("Library Database")
        mock_mw._select_tab_by_name.assert_called_once_with("Listings")

    def test_no_main_window_ref_shows_info_instead(self, q_app):
        tab = DatabaseTab()
        from PySide6.QtWidgets import QTableWidgetItem

        tab.tags_table.setRowCount(1)
        tab.tags_table.setItem(0, 0, QTableWidgetItem("sunset"))
        tab.tags_table.setCurrentCell(0, 0)
        tab.listings_tab_ref = MagicMock()
        tab.main_window_ref = None

        with patch(
            "gui.src.tabs.database.database_tab._crud.QMessageBox.information"
        ) as mock_info:
            tab.search_listings_with_selected_tag()
            mock_info.assert_called_once()


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
        mock_db_tab.db.get_all_tags_with_types.return_value = [
            {"name": "sunset", "type": "General"},
            {"name": "portrait", "type": "General"},
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
