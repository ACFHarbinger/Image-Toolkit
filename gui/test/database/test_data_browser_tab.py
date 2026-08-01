"""Tests for DataBrowserTab (gui/src/tabs/database/data_browser_tab/) — DB.9."""

from unittest.mock import MagicMock, patch

import pytest
from gui.src.tabs.database.data_browser_tab import DataBrowserTab
from gui.src.tabs.database.data_browser_tab._er_view import _TableCardItem
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsLineItem, QMessageBox, QWidget

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


class TestDataBrowserTabNavigation:
    """DB.9: FK-cell click-to-navigate + reverse-references panel."""

    def _make_tab_on_images(self, fks=None, pk_index_columns=None):
        tab = DataBrowserTab()
        tab.browser_repo = MagicMock()
        tab.current_table = "images"
        # Pre-seed every table a navigation test might jump to, the way
        # refresh_table_list() would in the real flow -- adding an item
        # to an empty QComboBox auto-selects it, firing currentTextChanged
        # (-> _on_table_changed -> _run_query, which clears refs_list) as
        # a side effect a test-time addItem() would otherwise trip.
        tab.table_combo.blockSignals(True)
        tab.table_combo.addItems(["images", "groups", "media_groups"])
        tab.table_combo.setCurrentText("images")
        tab.table_combo.blockSignals(False)
        tab.browser_repo.table_foreign_keys.return_value = fks or [
            {"column": "group_id", "ref_table": "groups", "ref_column": "id"},
        ]
        tab.browser_repo.table_columns.return_value = pk_index_columns or [
            {"name": "id", "type": "INTEGER", "notnull": True, "pk": True},
            {"name": "file_path", "type": "TEXT", "notnull": True, "pk": False},
            {"name": "group_id", "type": "INTEGER", "notnull": False, "pk": False},
        ]
        tab.browser_repo.query_table.return_value = (
            ["id", "file_path", "group_id"],
            [(1, "/a.png", 7), (2, "/b.png", None)],
        )
        tab._run_query()
        return tab

    def test_fk_metadata_cached_after_query(self, q_app):
        tab = self._make_tab_on_images()
        assert tab.fk_columns_by_index == {
            2: {"column": "group_id", "ref_table": "groups", "ref_column": "id"}
        }
        assert tab.pk_column_index == 0

    def test_fk_cell_click_navigates(self, q_app):
        tab = self._make_tab_on_images()
        # Clicking the "group_id" cell (col 2) of row 0 (value 7) should
        # switch to "groups" filtered to id = 7.
        tab.browser_repo.table_foreign_keys.return_value = []  # groups has none
        tab.browser_repo.query_table.return_value = (["id", "name"], [(7, "Trips")])

        tab._on_cell_clicked(0, 2)

        assert tab.current_table == "groups"
        assert tab.where_edit.text() == "id = 7"

    def test_fk_cell_click_on_null_value_is_noop(self, q_app):
        tab = self._make_tab_on_images()
        before_table = tab.current_table
        tab._on_cell_clicked(1, 2)  # row 1's group_id is None -> "" cell text
        assert tab.current_table == before_table

    def test_non_fk_cell_click_is_noop(self, q_app):
        tab = self._make_tab_on_images()
        tab._on_cell_clicked(0, 1)  # file_path column, not a FK
        assert tab.current_table == "images"

    def test_row_selection_populates_reverse_references(self, q_app):
        tab = self._make_tab_on_images()
        tab.browser_repo.reverse_references.return_value = [
            {"table": "media_groups", "column": "group_id", "count": 3},
        ]

        tab.data_table.selectRow(0)

        tab.browser_repo.reverse_references.assert_called_with("images", "1")
        assert tab.refs_list.count() == 1
        assert "media_groups.group_id (3)" in tab.refs_list.item(0).text()

    def test_row_selection_no_references_shows_hint(self, q_app):
        tab = self._make_tab_on_images()
        tab.browser_repo.reverse_references.return_value = []

        tab.data_table.selectRow(1)

        assert tab.refs_list.count() == 0
        assert "No other rows reference" in tab.refs_hint_label.text()

    def test_reverse_reference_click_navigates(self, q_app):
        tab = self._make_tab_on_images()
        tab.browser_repo.reverse_references.return_value = [
            {"table": "media_groups", "column": "group_id", "count": 3},
        ]
        tab.data_table.selectRow(0)
        tab.browser_repo.table_foreign_keys.return_value = []
        tab.browser_repo.query_table.return_value = (["media_item_id", "group_id"], [])

        tab._on_reverse_ref_clicked(tab.refs_list.item(0))

        assert tab.current_table == "media_groups"
        assert tab.where_edit.text() == "group_id = 1"


class TestDataBrowserTabSchemaView:
    """DB.9: Schema/ER sub-view -- table cards + relationship lines."""

    def _make_tab_with_schema(self):
        tab = DataBrowserTab()
        tab.browser_repo = MagicMock()
        tab.browser_repo.list_tables.return_value = ["images", "groups"]

        def columns_for(table):
            if table == "images":
                return [
                    {"name": "id", "type": "INTEGER", "notnull": True, "pk": True},
                    {"name": "group_id", "type": "INTEGER", "notnull": False, "pk": False},
                ]
            return [{"name": "id", "type": "INTEGER", "notnull": True, "pk": True}]

        def fks_for(table):
            if table == "images":
                return [{"column": "group_id", "ref_table": "groups", "ref_column": "id"}]
            return []

        tab.browser_repo.table_columns.side_effect = columns_for
        tab.browser_repo.table_foreign_keys.side_effect = fks_for
        return tab

    def test_er_view_builds_one_card_per_table(self, q_app):
        tab = self._make_tab_with_schema()
        tab._refresh_er_view()

        cards = [i for i in tab.er_scene.items() if isinstance(i, _TableCardItem)]
        assert {c.table_name for c in cards} == {"images", "groups"}

    def test_er_view_draws_relationship_line_for_fk(self, q_app):
        tab = self._make_tab_with_schema()
        tab._refresh_er_view()

        # Top-level lines only -- each card's title-divider is also a
        # QGraphicsLineItem, but parented to the card, not a relationship.
        lines = [
            i for i in tab.er_scene.items()
            if isinstance(i, QGraphicsLineItem) and i.parentItem() is None
        ]
        assert len(lines) >= 1

    def test_er_view_no_fk_no_relationship_line(self, q_app):
        tab = self._make_tab_with_schema()
        tab.browser_repo.table_foreign_keys.side_effect = None
        tab.browser_repo.table_foreign_keys.return_value = []
        tab._refresh_er_view()

        lines = [
            i for i in tab.er_scene.items()
            if isinstance(i, QGraphicsLineItem) and i.parentItem() is None
        ]
        assert lines == []

    def test_clicking_table_card_switches_to_grid_and_selects_table(self, q_app):
        tab = self._make_tab_with_schema()
        # setCurrentText("groups") below fires currentTextChanged ->
        # _on_table_changed -> _run_query(), which unpacks query_table()'s
        # return value -- an unconfigured MagicMock isn't iterable, and the
        # resulting exception pops a real, blocking QMessageBox in this
        # headless run. Configure the full cascade, not just list_tables.
        tab.browser_repo.table_row_count.return_value = 0
        tab.browser_repo.query_table.return_value = ([], [])
        tab.table_combo.blockSignals(True)
        tab.table_combo.addItems(["images", "groups"])
        tab.table_combo.blockSignals(False)
        tab.view_tabs.setCurrentIndex(1)  # Schema tab

        tab._on_er_table_clicked("groups")

        assert tab.view_tabs.currentIndex() == 0  # back to Grid
        assert tab.table_combo.currentText() == "groups"

    def test_refresh_table_list_also_populates_schema_view(self, q_app):
        tab = self._make_tab_with_schema()
        tab.browser_repo.table_row_count.return_value = 0
        tab.browser_repo.query_table.return_value = ([], [])

        tab.refresh_table_list()

        cards = [i for i in tab.er_scene.items() if isinstance(i, _TableCardItem)]
        assert len(cards) == 2


class TestDataBrowserTabEditMode:
    """DB.9: gated, session-only cell-edit mode."""

    def _make_tab_on_images(self):
        tab = DataBrowserTab()
        tab.browser_repo = MagicMock()
        tab.current_table = "images"
        tab.browser_repo.table_foreign_keys.return_value = [
            {"column": "group_id", "ref_table": "groups", "ref_column": "id"},
        ]
        tab.browser_repo.table_columns.return_value = [
            {"name": "id", "type": "INTEGER", "notnull": True, "pk": True},
            {"name": "file_path", "type": "TEXT", "notnull": True, "pk": False},
            {"name": "group_id", "type": "INTEGER", "notnull": False, "pk": False},
        ]
        tab.browser_repo.query_table.return_value = (
            ["id", "file_path", "group_id"],
            [(1, "/a.png", 7)],
        )
        tab._run_query()
        return tab

    def test_edit_mode_off_by_default_and_cells_not_editable(self, q_app):
        tab = self._make_tab_on_images()
        assert tab.edit_mode_enabled is False
        item = tab.data_table.item(0, 1)  # file_path -- not PK/FK
        assert not (item.flags() & Qt.ItemFlag.ItemIsEditable)

    def test_enabling_edit_mode_makes_non_pk_fk_cells_editable(self, q_app):
        tab = self._make_tab_on_images()
        tab.edit_mode_checkbox.setChecked(True)

        file_path_item = tab.data_table.item(0, 1)
        assert file_path_item.flags() & Qt.ItemFlag.ItemIsEditable

        pk_item = tab.data_table.item(0, 0)
        fk_item = tab.data_table.item(0, 2)
        assert not (pk_item.flags() & Qt.ItemFlag.ItemIsEditable)
        assert not (fk_item.flags() & Qt.ItemFlag.ItemIsEditable)

    def test_confirmed_edit_calls_update_cell_and_requeries(self, q_app):
        tab = self._make_tab_on_images()
        tab.edit_mode_checkbox.setChecked(True)

        with patch(
            "gui.src.tabs.database.data_browser_tab._edit.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            tab.data_table.item(0, 1).setText("/renamed.png")

        tab.browser_repo.update_cell.assert_called_once_with(
            "images", "id", "1", "file_path", "/renamed.png",
        )
        # _on_cell_changed() re-runs the query to reflect real DB state.
        assert tab.browser_repo.query_table.call_count == 2

    def test_cancelled_edit_reverts_cell_and_does_not_write(self, q_app):
        tab = self._make_tab_on_images()
        tab.edit_mode_checkbox.setChecked(True)

        with patch(
            "gui.src.tabs.database.data_browser_tab._edit.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            tab.data_table.item(0, 1).setText("/renamed.png")

        tab.browser_repo.update_cell.assert_not_called()
        assert tab.data_table.item(0, 1).text() == "/a.png"

    def test_edit_rejected_by_repo_reverts_cell(self, q_app):
        tab = self._make_tab_on_images()
        tab.edit_mode_checkbox.setChecked(True)
        tab.browser_repo.update_cell.side_effect = ValueError("nope")

        with patch(
            "gui.src.tabs.database.data_browser_tab._edit.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch(
            "gui.src.tabs.database.data_browser_tab._edit.QMessageBox.warning"
        ) as mock_warn:
            tab.data_table.item(0, 1).setText("/renamed.png")
            mock_warn.assert_called()

        assert tab.data_table.item(0, 1).text() == "/a.png"


class TestDataBrowserTabColumnFilters:
    """DB.9: per-column filter row, composed with the main WHERE box."""

    def _make_tab_on_images(self):
        tab = DataBrowserTab()
        tab.browser_repo = MagicMock()
        tab.current_table = "images"
        tab.browser_repo.table_foreign_keys.return_value = []
        tab.browser_repo.table_columns.return_value = [
            {"name": "id", "type": "INTEGER", "notnull": True, "pk": True},
            {"name": "file_path", "type": "TEXT", "notnull": True, "pk": False},
        ]
        tab.browser_repo.query_table.return_value = (
            ["id", "file_path"], [(1, "/a.png")],
        )
        tab._run_query()
        return tab

    def test_column_filter_row_built_for_current_columns(self, q_app):
        tab = self._make_tab_on_images()
        assert len(tab.column_filter_edits) == 2
        assert tab.column_filter_edits[1].placeholderText() == "file_path"

    def test_column_filter_composes_into_where_clause(self, q_app):
        tab = self._make_tab_on_images()
        tab.column_filter_edits[1].setText("a.png")

        tab._apply_filter()

        _, kwargs = tab.browser_repo.query_table.call_args
        assert kwargs["where_sql"] == "\"file_path\" LIKE '%a.png%'"

    def test_column_filter_composes_with_main_where_box(self, q_app):
        tab = self._make_tab_on_images()
        tab.where_edit.setText("id > 0")
        tab.column_filter_edits[1].setText("a.png")

        tab._apply_filter()

        _, kwargs = tab.browser_repo.query_table.call_args
        assert kwargs["where_sql"] == "(id > 0) AND \"file_path\" LIKE '%a.png%'"

    def test_table_switch_clears_column_filters(self, q_app):
        tab = self._make_tab_on_images()
        tab.column_filter_edits[1].setText("a.png")
        tab.browser_repo.query_table.return_value = (["id"], [])
        tab.browser_repo.table_row_count.return_value = 0

        tab._on_table_changed("groups")

        assert len(tab.column_filter_edits) == 1  # rebuilt for the new column set
        assert tab.column_filter_edits[0].text() == ""
