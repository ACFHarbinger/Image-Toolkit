"""Per-column filter row for the Data Browser grid -- DB.9.

Additive to (composes with, not a replacement for) the main free-text
WHERE box: each non-empty per-column field ANDs a LIKE condition for
that column into the same query_table(where_sql=...) call the WHERE box
already uses -- one query path, the combined WHERE text is built here in
the GUI layer, never a second query method on BrowserRepo.

Column filters reset whenever the table changes (the widgets are rebuilt
for the new column set on the next successful query) -- there is no
cross-table "which filter belongs to which now-gone column" state to
carry over.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtWidgets import QLineEdit

from ._navigation import _sql_literal


class _FiltersMixin:
    """Per-column filter fields, composed with the main WHERE box."""

    def _clear_column_filters(self) -> None:
        for edit in self.column_filter_edits:
            edit.setParent(None)
            edit.deleteLater()
        self.column_filter_edits = []

    def _rebuild_column_filters(self, columns: List[str]) -> None:
        self._clear_column_filters()
        for name in columns:
            edit = QLineEdit()
            edit.setPlaceholderText(name)
            edit.returnPressed.connect(self._apply_filter)
            self.column_filter_layout.addWidget(edit)
            self.column_filter_edits.append(edit)

    def _compose_where(self) -> Optional[str]:
        conditions = []
        base = self.where_edit.text().strip()
        if base:
            conditions.append(f"({base})")

        for idx, edit in enumerate(self.column_filter_edits):
            text = edit.text().strip()
            if not text or idx >= len(self.current_columns):
                continue
            column_name = self.current_columns[idx]
            like_value = _sql_literal(f"%{text}%")
            conditions.append(f'"{column_name}" LIKE {like_value}')

        return " AND ".join(conditions) if conditions else None


__all__ = ["_FiltersMixin"]
