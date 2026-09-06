"""Image-registry UI section builder for ``DatabaseTab`` (§5.17, #544)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
)

from ....styles import apply_shadow_effect

if TYPE_CHECKING:
    pass


def build_registry_section(tab: Any, populate_layout: QVBoxLayout) -> None:
    """Build the "Image Registry" section (all indexed paths + filter bar) onto tab."""
    image_registry_group = QGroupBox("Image Registry")
    image_registry_layout = QVBoxLayout(image_registry_group)

    registry_header = QHBoxLayout()
    registry_info = QLabel(
        "All image paths currently indexed in the database, with their associated group and subgroup."
    )
    registry_info.setStyleSheet("color: #aaa; font-style: italic; font-size: 12px;")
    registry_info.setWordWrap(True)
    registry_header.addWidget(registry_info, 1)

    tab.btn_refresh_registry = QPushButton("↻ Refresh")
    apply_shadow_effect(
        tab.btn_refresh_registry, color_hex="#000000", radius=8, x_offset=0, y_offset=3
    )
    tab.btn_refresh_registry.clicked.connect(tab.refresh_image_registry)
    registry_header.addWidget(tab.btn_refresh_registry)
    image_registry_layout.addLayout(registry_header)

    # Filter bar
    filter_row = QHBoxLayout()
    filter_row.addWidget(QLabel("Filter:"))
    tab.registry_filter_edit = QLineEdit()
    tab.registry_filter_edit.setPlaceholderText(
        "Type to filter by path, group or subgroup…"
    )
    tab.registry_filter_edit.textChanged.connect(tab._apply_registry_filter)
    filter_row.addWidget(tab.registry_filter_edit, 1)
    image_registry_layout.addLayout(filter_row)

    # Table
    tab.image_registry_table = QTableWidget()
    tab.image_registry_table.setColumnCount(3)
    tab.image_registry_table.setHorizontalHeaderLabels(
        ["File Path", "Group", "Subgroup"]
    )
    tab.image_registry_table.horizontalHeader().setSectionResizeMode(
        0, QHeaderView.ResizeMode.Stretch
    )
    tab.image_registry_table.horizontalHeader().setSectionResizeMode(
        1, QHeaderView.ResizeMode.ResizeToContents
    )
    tab.image_registry_table.horizontalHeader().setSectionResizeMode(
        2, QHeaderView.ResizeMode.ResizeToContents
    )
    tab.image_registry_table.setAlternatingRowColors(True)
    tab.image_registry_table.setSelectionBehavior(
        QAbstractItemView.SelectionBehavior.SelectRows
    )
    tab.image_registry_table.setSelectionMode(
        QAbstractItemView.SelectionMode.SingleSelection
    )
    tab.image_registry_table.setEditTriggers(
        QAbstractItemView.EditTrigger.NoEditTriggers
    )
    tab.image_registry_table.setStyleSheet(tab.groups_table.styleSheet())
    tab.image_registry_table.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    tab.image_registry_table.setMinimumHeight(260)
    tab.image_registry_table.setSortingEnabled(True)
    tab.image_registry_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tab.image_registry_table.customContextMenuRequested.connect(
        tab._show_registry_context_menu
    )

    image_registry_layout.addWidget(tab.image_registry_table)
    populate_layout.addWidget(image_registry_group)

    # Internal cache for filter support
    tab._registry_rows = []  # (path, group, subgroup)


class DatabaseRegistryUIBuilder:
    """Builder for the registry section."""

    def __init__(self, tab: Any) -> None:
        self.tab = tab

    def build(self, populate_layout: QVBoxLayout) -> None:
        build_registry_section(self.tab, populate_layout)


class _UIRegistryMixin:
    """Backward-compatible mixin adapter."""

    def _build_registry_section(self, populate_layout: QVBoxLayout) -> None:
        build_registry_section(self, populate_layout)


__all__ = ["DatabaseRegistryUIBuilder", "_UIRegistryMixin", "build_registry_section"]
