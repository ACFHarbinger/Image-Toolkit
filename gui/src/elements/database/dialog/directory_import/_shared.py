"""Shared UI helpers for series and entity directory-import dialogs."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from gui.src.constants.listings import STATUS_COLORS
from gui.src.theming.theme_api import qss


def make_results_table(headers: list[str], stretch_columns: tuple[int, ...] = ()) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    for column in stretch_columns:
        table.horizontalHeader().setSectionResizeMode(
            column, QHeaderView.ResizeMode.Stretch
        )
    table.setColumnWidth(0, 32)
    table.setColumnWidth(len(headers) - 1, 120)
    table.verticalHeader().hide()
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(True)
    table.setStyleSheet(qss("directory_import_table"))
    return table


def make_checkbox_cell(checked: bool) -> QWidget:
    chk = QCheckBox()
    chk.setChecked(checked)
    chk.setStyleSheet(qss("directory_import_checkbox"))
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.addWidget(chk)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.setContentsMargins(0, 0, 0, 0)
    return container


def make_status_item(already_exists: bool) -> QTableWidgetItem:
    if already_exists:
        item = QTableWidgetItem("⚠ Already exists")
        item.setForeground(QColor(STATUS_COLORS["On Hold"]))
    else:
        item = QTableWidgetItem("✓ New")
        item.setForeground(QColor(STATUS_COLORS["Completed"]))
    return item


def build_selection_button_row(
    select_all_cb,
    deselect_all_cb,
) -> QHBoxLayout:
    row = QHBoxLayout()
    select_all_btn = QPushButton("☑ Select All New")
    select_all_btn.setFixedHeight(36)
    select_all_btn.setStyleSheet(qss("directory_import_btn_padding"))
    select_all_btn.clicked.connect(select_all_cb)
    deselect_all_btn = QPushButton("☐ Deselect All")
    deselect_all_btn.setFixedHeight(36)
    deselect_all_btn.setStyleSheet(qss("directory_import_btn_padding"))
    deselect_all_btn.clicked.connect(deselect_all_cb)
    row.addWidget(select_all_btn)
    row.addWidget(deselect_all_btn)
    row.addStretch()
    return row


def build_confirm_button_row(import_btn: QPushButton, reject_cb) -> QHBoxLayout:
    row = QHBoxLayout()
    row.addStretch()
    cancel_btn = QPushButton("Cancel")
    cancel_btn.setFixedWidth(90)
    cancel_btn.clicked.connect(reject_cb)
    import_btn.setStyleSheet(qss("shared_button"))
    import_btn.setFixedWidth(150)
    import_btn.setEnabled(False)
    row.addWidget(cancel_btn)
    row.addWidget(import_btn)
    return row


__all__ = [
    "build_confirm_button_row",
    "build_selection_button_row",
    "make_checkbox_cell",
    "make_results_table",
    "make_status_item",
]
