"""Tab-config persistence (``collect``/``get_default_config``/``set_config``).

R1.2 / #557: the raw-table browser joins the TabConfig contract so Ctrl+S
snapshots, workflow templates, and session recovery restore its working
view. Edit mode is deliberately *not* persisted -- it is a session-only
gate (see the checkbox tooltip and the manager docstring).
"""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtWidgets import QMessageBox

from ._tab_bound import TabBoundController


class DataBrowserConfigController(TabBoundController):
    """Save/restore the browsing view: selected table, WHERE box, per-column filters."""

    def collect(self) -> Dict[str, Any]:
        return {
            "table": self.table_combo.currentText() or None,
            "where": self.where_edit.text().strip() or None,
            "column_filters": {
                column: edit.text().strip()
                for column, edit in zip(self.current_columns, self.column_filter_edits, strict=False)
                if edit.text().strip()
            }
            or None,
        }

    def get_default_config(self) -> Dict[str, Any]:
        return {"table": None, "where": None, "column_filters": None}

    def set_config(self, config: Dict[str, Any]):
        try:
            # Select the saved table first: _on_table_changed clears the WHERE
            # box and per-column filters, so they are restored after this.
            table = config.get("table") or ""
            if table and self.table_combo.findText(table) != -1:
                self.table_combo.setCurrentText(table)

            self.where_edit.setText(config.get("where") or "")
            saved_filters = config.get("column_filters") or {}

            def _apply_saved_filters():
                for column, text in saved_filters.items():
                    if column in self.current_columns:
                        idx = self.current_columns.index(column)
                        if idx < len(self.column_filter_edits):
                            self.column_filter_edits[idx].setText(text)

            # A query rebuilds the per-column filter row (_populate_grid ->
            # _rebuild_column_filters), which wipes any texts already in it --
            # so the texts go in before the composing query AND again after
            # it, leaving the restored view showing them (same end state as a
            # user who just applied filters manually).
            _apply_saved_filters()
            if self.where_edit.text() or saved_filters:
                self._apply_filter()
                _apply_saved_filters()
            print("DataBrowserTab configuration loaded.")
        except Exception as e:
            print(f"Error applying DataBrowserTab config: {e}")
            QMessageBox.warning(self.tab, "Config Error", f"Failed to apply some settings: {e}")


__all__ = ["DataBrowserConfigController"]
