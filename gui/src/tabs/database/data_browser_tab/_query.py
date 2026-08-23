"""Connection lifecycle, table listing, and paginated query dispatch for
``DataBrowserTab``.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QTableWidgetItem


class _QueryMixin:
    """Open the store, list tables, and run/paginate the read-only grid query."""

    def connect_browser(self, silent: bool = False) -> None:
        from backend.src.database.unified.browser_repo import BrowserRepo

        from gui.src.helpers.database.library_session import get_library_db

        try:
            session_db = get_library_db(self.vault_manager, parent=self)
            if session_db is None:
                if not silent:
                    QMessageBox.warning(
                        self,
                        "Vault Locked",
                        "The Data Browser requires an unlocked vault. Log "
                        "in first, then reopen this tab.",
                    )
                self._set_controls_enabled(False)
                return

            self.browser_repo = BrowserRepo(session_db)
            self.refresh_table_list()
            self._set_controls_enabled(True)
        except Exception as e:
            if not silent:
                QMessageBox.critical(
                    self, "Error", f"Failed to open the library database:\n{e}"
                )
            self._set_controls_enabled(False)

    def refresh_table_list(self) -> None:
        if not self.browser_repo:
            return
        try:
            tables = self.browser_repo.list_tables()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to list tables:\n{e}")
            return

        previous = self.table_combo.currentText()
        self.table_combo.blockSignals(True)
        self.table_combo.clear()
        self.table_combo.addItems(tables)
        self.table_combo.blockSignals(False)

        if previous in tables:
            self.table_combo.setCurrentText(previous)
        elif tables:
            self.table_combo.setCurrentText(tables[0])
            self._on_table_changed(tables[0])

        self._refresh_er_view()

    def _on_table_changed(self, table_name: str) -> None:
        if not table_name or not self.browser_repo:
            return
        self.current_table = table_name
        self.current_offset = 0
        self.where_edit.clear()
        self._clear_column_filters()
        self._refresh_row_count()
        self._run_query()

    def _refresh_row_count(self) -> None:
        if not self.browser_repo or not self.current_table:
            return
        try:
            self.current_row_count = self.browser_repo.table_row_count(self.current_table)
            self.row_count_label.setText(f"{self.current_row_count} row(s)")
        except Exception as e:
            self.row_count_label.setText(f"Error: {e}")

    def _apply_filter(self) -> None:
        self.current_offset = 0
        self._run_query()

    def _clear_filter(self) -> None:
        self.where_edit.clear()
        self.current_offset = 0
        self._run_query()

    def _prev_page(self) -> None:
        if self.current_offset <= 0:
            return
        self.current_offset = max(0, self.current_offset - self.PAGE_SIZE)
        self._run_query()

    def _next_page(self) -> None:
        self.current_offset += self.PAGE_SIZE
        self._run_query()

    def _run_query(self) -> None:
        if not self.browser_repo or not self.current_table:
            return
        where_sql = self._compose_where()
        try:
            columns, rows = self.browser_repo.query_table(
                self.current_table,
                where_sql=where_sql,
                limit=self.PAGE_SIZE,
                offset=self.current_offset,
            )
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Filter", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Query Error", str(e))
            return

        self.current_columns = columns
        self.current_rows = rows
        self._refresh_fk_metadata()
        self._populate_grid(columns, rows)
        self.refs_list.clear()
        self.refs_hint_label.setText("Select a row to see incoming references.")
        self.refs_hint_label.show()

        page_number = (self.current_offset // self.PAGE_SIZE) + 1
        self.page_label.setText(f"Page {page_number}")
        self.btn_prev_page.setEnabled(self.current_offset > 0)
        self.btn_next_page.setEnabled(len(rows) == self.PAGE_SIZE)

    def _populate_grid(self, columns: list, rows: list) -> None:
        # Blocked for the whole population: setItem()/clear()/setRowCount()
        # would otherwise fire cellChanged/itemSelectionChanged as a side
        # effect of programmatic population, not a real user edit or
        # selection -- see _edit.py's _on_cell_changed().
        self.data_table.blockSignals(True)
        try:
            self.data_table.setSortingEnabled(False)
            self.data_table.clear()
            self.data_table.setColumnCount(len(columns))
            self.data_table.setHorizontalHeaderLabels(columns)
            self.data_table.setRowCount(len(rows))
            for row_idx, row in enumerate(rows):
                for col_idx, value in enumerate(row):
                    item = QTableWidgetItem("" if value is None else str(value))
                    self.data_table.setItem(row_idx, col_idx, item)
            self.data_table.setSortingEnabled(True)
            self._style_fk_cells()
            self._apply_cell_edit_flags()
            self._rebuild_column_filters(columns)
        finally:
            self.data_table.blockSignals(False)


__all__ = ["_QueryMixin"]
