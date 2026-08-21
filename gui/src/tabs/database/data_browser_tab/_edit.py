"""Gated, per-session cell-edit mode for the Data Browser grid -- DB.9.

Off by default every time the tab is (re)opened, never persisted across
sessions -- an explicit per-view opt-in, not a saved preference. Scoped
strictly to single-cell, single-column, scalar edits with a confirmation
prompt before every write: this is NOT a general SQL editor. PK and FK
columns stay non-editable regardless of edit mode -- BrowserRepo.
update_cell() itself refuses those edits too (see its docstring); the
restriction here is UX (don't even offer it), not the real safety
boundary.

The roadmap's original text said edit mode should wait "until the
read-only browser has soaked" -- real-world usage proving the read path
safe before allowing writes. That soak time has not actually elapsed
(this ships in the same development arc as the read-only browser
itself), so every remaining safety margin the "gated" framing implies is
kept here: off by default, one cell at a time, human-confirmed before
every write, and the grid re-queries the real DB state after a write
rather than trusting the in-memory edit.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox


class _EditMixin:
    """Edit-mode toggle + confirmed, validated single-cell writes."""

    def _on_edit_mode_toggled(self, checked: bool) -> None:
        self.edit_mode_enabled = checked
        self._apply_cell_edit_flags()

    def _apply_cell_edit_flags(self) -> None:
        """(Re)apply per-cell editable flags to the current grid -- PK and
        FK columns are never made editable, regardless of edit mode."""
        non_editable = set(self.fk_columns_by_index)
        if self.pk_column_index is not None:
            non_editable.add(self.pk_column_index)

        for row in range(self.data_table.rowCount()):
            for col in range(self.data_table.columnCount()):
                item = self.data_table.item(row, col)
                if item is None:
                    continue
                flags = item.flags()
                if self.edit_mode_enabled and col not in non_editable:
                    item.setFlags(flags | Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(flags & ~Qt.ItemFlag.ItemIsEditable)

    def _on_cell_changed(self, row: int, col: int) -> None:
        if not self.edit_mode_enabled or self.pk_column_index is None:
            return
        if col == self.pk_column_index or col in self.fk_columns_by_index:
            return  # not reachable via the UI (not editable) -- defense in depth

        item = self.data_table.item(row, col)
        if item is None:
            return
        new_value = item.text()

        old_value = self.current_rows[row][col] if row < len(self.current_rows) else None
        old_text = "" if old_value is None else str(old_value)
        if new_value == old_text:
            return

        pk_item = self.data_table.item(row, self.pk_column_index)
        pk_value = pk_item.text() if pk_item is not None else None
        column_name = self.current_columns[col]
        pk_column_name = self.current_columns[self.pk_column_index]

        confirm = QMessageBox.question(
            self,
            "Confirm Edit",
            f"Change {column_name!r} from {old_text!r} to {new_value!r} "
            f"for {pk_column_name} = {pk_value!r}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            self._revert_cell(row, col, old_text)
            return

        try:
            self.browser_repo.update_cell(
                self.current_table, pk_column_name, pk_value, column_name, new_value,
            )
        except ValueError as e:
            QMessageBox.warning(self, "Edit Rejected", str(e))
            self._revert_cell(row, col, old_text)
            return
        except Exception as e:
            QMessageBox.critical(self, "Edit Failed", str(e))
            self._revert_cell(row, col, old_text)
            return

        # Reflect the real DB state rather than trusting the in-memory
        # edit -- also re-derives fk/pk metadata and reapplies edit flags.
        self._run_query()

    def _revert_cell(self, row: int, col: int, original_text: str) -> None:
        item = self.data_table.item(row, col)
        if item is None:
            return
        self.data_table.blockSignals(True)
        item.setText(original_text)
        self.data_table.blockSignals(False)


__all__ = ["_EditMixin"]
