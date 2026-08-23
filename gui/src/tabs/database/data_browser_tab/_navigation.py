"""FK-cell click-to-navigate and the reverse-references side panel for
``DataBrowserTab`` -- DB.9.

FK columns are detected via ``BrowserRepo.table_foreign_keys()`` (cached
per table-load in ``self.current_fks``) and styled to signal they're
navigable; clicking one switches the table picker to the referenced
table and filters to the clicked value. The reverse-references panel
does the mirror image: for the selected row's primary-key value, it
lists every OTHER table/column that references it, each entry itself
clickable to navigate the same way.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush
from PySide6.QtWidgets import QListWidgetItem, QMessageBox

from gui.src.constants.elements import _FK_CELL_COLOR


def _sql_literal(value: Any) -> str:
    """Format *value* as a literal for the (unparameterized) WHERE-clause
    text query_table() accepts -- integers bare, everything else quoted
    as a single-quote-escaped SQL string literal."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    try:
        int(text)
    except ValueError:
        return "'" + text.replace("'", "''") + "'"
    return text


class _NavigationMixin:
    """FK-cell navigation + reverse-references panel."""

    def _refresh_fk_metadata(self) -> None:
        """Cache this table's FK columns (by index into self.current_columns)
        and its primary-key column name, both needed by the handlers below.
        Called after every successful query (self.current_columns is fresh)."""
        self.current_fks = []
        self.fk_columns_by_index = {}
        self.pk_column_index: Optional[int] = None
        if not self.browser_repo or not self.current_table:
            return
        try:
            self.current_fks = self.browser_repo.table_foreign_keys(self.current_table)
            columns_meta = self.browser_repo.table_columns(self.current_table)
        except Exception:
            return

        fk_by_column = {fk["column"]: fk for fk in self.current_fks}
        for idx, name in enumerate(self.current_columns):
            if name in fk_by_column:
                self.fk_columns_by_index[idx] = fk_by_column[name]

        pk_names = [c["name"] for c in columns_meta if c["pk"]]
        if len(pk_names) == 1 and pk_names[0] in self.current_columns:
            self.pk_column_index = self.current_columns.index(pk_names[0])

    def _style_fk_cells(self) -> None:
        """Underline + color FK-column cells so they read as navigable,
        without disturbing normal selection/sorting for other columns."""
        if not self.fk_columns_by_index:
            return
        for row_idx in range(self.data_table.rowCount()):
            for col_idx in self.fk_columns_by_index:
                item = self.data_table.item(row_idx, col_idx)
                if item is None:
                    continue
                font = item.font()
                font.setUnderline(True)
                item.setFont(font)
                item.setForeground(QBrush(_FK_CELL_COLOR))
                item.setToolTip(
                    f"References {self.fk_columns_by_index[col_idx]['ref_table']}"
                    f".{self.fk_columns_by_index[col_idx]['ref_column']} -- click to jump"
                )

    def _on_cell_clicked(self, row: int, col: int) -> None:
        fk = self.fk_columns_by_index.get(col)
        if not fk:
            return
        item = self.data_table.item(row, col)
        if item is None or item.text() == "":
            return
        self._navigate_to(fk["ref_table"], fk["ref_column"], item.text())

    def _on_row_selection_changed(self) -> None:
        self.refs_list.clear()
        if self.pk_column_index is None:
            self.refs_hint_label.setText("This table has no single-column primary key.")
            self.refs_hint_label.show()
            return

        selected_rows = self.data_table.selectionModel().selectedRows() if self.data_table.selectionModel() else []
        if not selected_rows:
            self.refs_hint_label.setText("Select a row to see incoming references.")
            self.refs_hint_label.show()
            return

        row = selected_rows[0].row()
        pk_item = self.data_table.item(row, self.pk_column_index)
        if pk_item is None:
            return
        pk_value = pk_item.text()

        try:
            refs = self.browser_repo.reverse_references(self.current_table, pk_value)
        except Exception as e:
            self.refs_hint_label.setText(f"Error: {e}")
            self.refs_hint_label.show()
            return

        if not refs:
            self.refs_hint_label.setText("No other rows reference this one.")
            self.refs_hint_label.show()
            return

        self.refs_hint_label.hide()
        for ref in refs:
            label = f"{ref['table']}.{ref['column']} ({ref['count']})"
            list_item = QListWidgetItem(label)
            list_item.setData(Qt.ItemDataRole.UserRole, (ref["table"], ref["column"], pk_value))
            self.refs_list.addItem(list_item)

    def _on_reverse_ref_clicked(self, item: QListWidgetItem) -> None:
        table, column, pk_value = item.data(Qt.ItemDataRole.UserRole)
        self._navigate_to(table, column, pk_value)

    def _navigate_to(self, table: str, column: str, value: Any) -> None:
        """Switch to *table*, filtered to rows where *column* == *value* --
        the shared jump used by both FK-cell clicks and the reverse-
        references panel."""
        if not self.browser_repo:
            return
        tables = [self.table_combo.itemText(i) for i in range(self.table_combo.count())]
        if table not in tables:
            QMessageBox.warning(
                self, "Navigate", f"Table {table!r} is not available in this store."
            )
            return

        self.table_combo.setCurrentText(table)  # triggers _on_table_changed if it changed
        if self.current_table != table:
            self._on_table_changed(table)
        self.current_offset = 0
        self.where_edit.setText(f"{column} = {_sql_literal(value)}")
        self._run_query()


__all__ = ["_NavigationMixin"]
