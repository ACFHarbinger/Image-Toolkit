"""Keyboard shortcut discovery overlay (Ctrl+/ or F1) (§2.25A).

Extracted from ``main_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHeaderView, QLineEdit, QTableWidget, QTableWidgetItem, QVBoxLayout

from ...utils.manager.shortcut_manager import get_registry


class _ShortcutOverlayMixin:
    """Displays every registered keyboard shortcut in a searchable table."""

    def _open_shortcut_overlay(self) -> None:
        reg = get_registry()
        all_actions = reg.get_all()

        dlg = QDialog(self)
        dlg.setWindowTitle("Keyboard Shortcuts  (Ctrl+/)")
        dlg.resize(560, 460)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        search = QLineEdit()
        search.setPlaceholderText("Filter shortcuts…")
        layout.addWidget(search)

        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Scope", "Action", "Key"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        layout.addWidget(table)

        def _populate(text: str = "") -> None:
            q = text.strip().lower()
            table.setRowCount(0)
            for entry in all_actions:
                if (
                    q
                    and q not in entry["description"].lower()
                    and q not in entry["current"].lower()
                    and q not in entry["scope"].lower()
                ):
                    continue
                row = table.rowCount()
                table.insertRow(row)
                for col, val in enumerate([entry["scope"], entry["description"], entry["current"]]):
                    item = QTableWidgetItem(val)
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    table.setItem(row, col, item)

        search.textChanged.connect(_populate)
        _populate()
        dlg.exec()


__all__ = ["_ShortcutOverlayMixin"]
