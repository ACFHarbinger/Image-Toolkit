"""Image-registry UI section builder for ``DatabaseTab``.

Extracted from ``DatabaseTab.__init__`` -- pure code motion, no logic change
(see ``_ui_connection.py``'s docstring). Assumes ``self.groups_table`` already
exists (``_build_groups_section`` runs first) -- its stylesheet is reused for
visual consistency, matching the original inline code.
"""

from __future__ import annotations

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

from ...styles import apply_shadow_effect


class _UIRegistryMixin:
    """Builds the "Image Registry" section (all indexed paths + filter bar)."""

    def _build_registry_section(self, populate_layout) -> None:
        image_registry_group = QGroupBox("Image Registry")
        image_registry_layout = QVBoxLayout(image_registry_group)

        registry_header = QHBoxLayout()
        registry_info = QLabel(
            "All image paths currently indexed in the database, with their associated group and subgroup."
        )
        registry_info.setStyleSheet("color: #aaa; font-style: italic; font-size: 12px;")
        registry_info.setWordWrap(True)
        registry_header.addWidget(registry_info, 1)

        self.btn_refresh_registry = QPushButton("↻ Refresh")
        apply_shadow_effect(
            self.btn_refresh_registry, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_refresh_registry.clicked.connect(self.refresh_image_registry)
        registry_header.addWidget(self.btn_refresh_registry)
        image_registry_layout.addLayout(registry_header)

        # Filter bar
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self.registry_filter_edit = QLineEdit()
        self.registry_filter_edit.setPlaceholderText(
            "Type to filter by path, group or subgroup…"
        )
        self.registry_filter_edit.textChanged.connect(self._apply_registry_filter)
        filter_row.addWidget(self.registry_filter_edit, 1)
        image_registry_layout.addLayout(filter_row)

        # Table
        self.image_registry_table = QTableWidget()
        self.image_registry_table.setColumnCount(3)
        self.image_registry_table.setHorizontalHeaderLabels(
            ["File Path", "Group", "Subgroup"]
        )
        self.image_registry_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.image_registry_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.image_registry_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.image_registry_table.setAlternatingRowColors(True)
        self.image_registry_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.image_registry_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.image_registry_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.image_registry_table.setStyleSheet(self.groups_table.styleSheet())
        self.image_registry_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.image_registry_table.setMinimumHeight(260)
        self.image_registry_table.setSortingEnabled(True)
        self.image_registry_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.image_registry_table.customContextMenuRequested.connect(
            self._show_registry_context_menu
        )

        image_registry_layout.addWidget(self.image_registry_table)
        populate_layout.addWidget(image_registry_group)

        # Internal cache for filter support
        self._registry_rows: list[tuple[str, str, str]] = []  # (path, group, subgroup)


__all__ = ["_UIRegistryMixin"]
