"""Tests for DataBrowserTab (gui/src/tabs/database/data_browser_tab/) — DB.9."""

from unittest.mock import MagicMock, patch

import pytest
from gui.src.tabs.database.data_browser_tab import DataBrowserTab
from PySide6.QtWidgets import QWidget

pytestmark = pytest.mark.gui


class TestDataBrowserTab:
    def test_init_no_vault(self, q_app):
        tab = DataBrowserTab()
        assert isinstance(tab, QWidget)
        assert tab.browser_repo is None
        assert tab.table_combo.isEnabled() is False

    def test_connect_browser_no_vault_shows_warning(self, q_app):
        tab = DataBrowserTab()
        with patch(
            "gui.src.helpers.database.library_session.get_library_db",
            return_value=None,
        ), patch(
            "gui.src.tabs.database.data_browser_tab._query.QMessageBox.warning"
        ) as mock_warn:
            tab.connect_browser(silent=False)
            mock_warn.assert_called()
        assert tab.browser_repo is None

    def test_connect_browser_populates_table_list(self, q_app):
        tab = DataBrowserTab()
        mock_repo = MagicMock()
        mock_repo.list_tables.return_value = ["images", "media_items", "tags"]
        # refresh_table_list() auto-selects the first table and cascades
        # into _on_table_changed() -> _run_query(), which unpacks
        # query_table()'s return value -- an unconfigured MagicMock isn't
        # iterable, so leaving these unset raises inside _run_query() and
        # pops a real, blocking QMessageBox.critical() in this headless
        # test run (hangs forever waiting for a click that never comes).
        mock_repo.table_row_count.return_value = 0
        mock_repo.query_table.return_value = ([], [])

        with patch(
            "gui.src.helpers.database.library_session.get_library_db",
            return_value=MagicMock(),
        ), patch(
            "backend.src.database.unified.browser_repo.BrowserRepo",
            return_value=mock_repo,
        ):
            tab.connect_browser(silent=True)

        assert tab.browser_repo is mock_repo
        assert tab.table_combo.isEnabled() is True
        items = [tab.table_combo.itemText(i) for i in range(tab.table_combo.count())]
        assert items == ["images", "media_items", "tags"]

    def test_table_change_runs_query_and_populates_grid(self, q_app):
        tab = DataBrowserTab()
        tab.browser_repo = MagicMock()
        tab.browser_repo.table_row_count.return_value = 2
        tab.browser_repo.query_table.return_value = (
            ["id", "file_path"],
            [(1, "/a.png"), (2, "/b.png")],
        )

        tab._on_table_changed("images")

        assert tab.current_table == "images"
        assert tab.data_table.columnCount() == 2
        assert tab.data_table.rowCount() == 2
        assert tab.data_table.item(0, 1).text() == "/a.png"
        assert tab.row_count_label.text() == "2 row(s)"

    def test_invalid_where_clause_shows_warning_not_crash(self, q_app):
        tab = DataBrowserTab()
        tab.browser_repo = MagicMock()
        tab.current_table = "images"
        tab.browser_repo.query_table.side_effect = ValueError("WHERE clause rejected")

        with patch(
            "gui.src.tabs.database.data_browser_tab._query.QMessageBox.warning"
        ) as mock_warn:
            tab.where_edit.setText("1=1; DROP TABLE images")
            tab._apply_filter()
            mock_warn.assert_called()

    def test_pagination_next_prev(self, q_app):
        tab = DataBrowserTab()
        tab.browser_repo = MagicMock()
        tab.current_table = "images"
        # Full page -> next enabled; then a short page -> next disabled.
        tab.browser_repo.query_table.return_value = (
            ["id"], [(i,) for i in range(tab.PAGE_SIZE)],
        )
        tab._run_query()
        assert tab.current_offset == 0
        assert tab.btn_next_page.isEnabled() is True
        assert tab.btn_prev_page.isEnabled() is False

        tab._next_page()
        assert tab.current_offset == tab.PAGE_SIZE

        tab.browser_repo.query_table.return_value = (["id"], [(1,)])
        tab._run_query()
        assert tab.btn_next_page.isEnabled() is False
        assert tab.btn_prev_page.isEnabled() is True

    def test_export_csv_writes_current_grid(self, q_app, tmp_path):
        tab = DataBrowserTab()
        tab.current_columns = ["id", "file_path"]
        tab.current_rows = [(1, "/a.png"), (2, "/b.png")]
        tab.current_table = "images"

        out_path = tmp_path / "out.csv"
        with patch(
            "gui.src.tabs.database.data_browser_tab._export.QFileDialog.getSaveFileName",
            return_value=(str(out_path), "CSV Files (*.csv)"),
        ), patch(
            "gui.src.tabs.database.data_browser_tab._export.QMessageBox.information"
        ):
            tab.export_csv()

        content = out_path.read_text()
        assert "id,file_path" in content
        assert "/a.png" in content

    def test_export_json_writes_current_grid(self, q_app, tmp_path):
        tab = DataBrowserTab()
        tab.current_columns = ["id", "file_path"]
        tab.current_rows = [(1, "/a.png")]
        tab.current_table = "images"

        out_path = tmp_path / "out.json"
        with patch(
            "gui.src.tabs.database.data_browser_tab._export.QFileDialog.getSaveFileName",
            return_value=(str(out_path), "JSON Files (*.json)"),
        ), patch(
            "gui.src.tabs.database.data_browser_tab._export.QMessageBox.information"
        ):
            tab.export_json()

        import json

        data = json.loads(out_path.read_text())
        assert data == [{"id": 1, "file_path": "/a.png"}]
