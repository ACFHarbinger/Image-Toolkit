"""Group-management UI section builder for ``DatabaseTab``.

Extracted from ``DatabaseTab.__init__`` -- pure code motion, no logic change
(see ``_ui_connection.py``'s docstring).
"""

from __future__ import annotations

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
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
from gui.src.constants.elements import _TABLE_STYLE


class _UIGroupsMixin:
    """Builds the auto-populate, create-group, and existing-groups sections."""

    def _build_groups_section(self, populate_layout) -> None:
        # -------------------------------------------------------------
        # Auto-Populate Button
        # -------------------------------------------------------------
        auto_pop_group = QGroupBox("Automatic Population")
        auto_pop_layout = QVBoxLayout(auto_pop_group)

        lbl_auto_info = QLabel(
            f"Scans <b>{LOCAL_SOURCE_PATH}</b>.<br>Top-level folders become Groups. Second-level folders become Subgroups."
        )
        lbl_auto_info.setStyleSheet("color: #aaa; font-style: italic;")
        auto_pop_layout.addWidget(lbl_auto_info)

        self.btn_auto_populate = QPushButton(
            "Auto-Sync Groups and Subgroups from Source"
        )
        self.btn_auto_populate.setStyleSheet(
            "background-color: #2ecc71; color: white; padding: 8px; font-weight: bold;"
        )
        apply_shadow_effect(
            self.btn_auto_populate,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.btn_auto_populate.clicked.connect(self.auto_populate_from_source)
        auto_pop_layout.addWidget(self.btn_auto_populate)

        populate_layout.addWidget(auto_pop_group)
        # -------------------------------------------------------------

        # --- Create New Group section ---
        create_group_group = QGroupBox("Create Group(s)")
        create_group_layout = QFormLayout(create_group_group)

        self.new_group_name_edit = QLineEdit()
        self.new_group_name_edit.setPlaceholderText(
            "group1, group2, group3 ... (comma-separated)"
        )
        create_group_layout.addRow("Group Name(s):", self.new_group_name_edit)

        self.btn_create_group = QPushButton("Create Group(s)")
        apply_shadow_effect(
            self.btn_create_group, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_create_group.clicked.connect(self.create_new_group)
        create_group_layout.addRow(self.btn_create_group)

        self.new_group_name_edit.returnPressed.connect(self.btn_create_group.click)
        populate_layout.addWidget(create_group_group)

        # --- Existing Groups section ---
        existing_groups_group = QGroupBox("Existing Groups")
        existing_groups_layout = QVBoxLayout(existing_groups_group)

        groups_btn_layout = QHBoxLayout()
        self.btn_refresh_groups = QPushButton("Refresh List")
        apply_shadow_effect(
            self.btn_refresh_groups,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.btn_refresh_groups.clicked.connect(self.refresh_groups_list)
        groups_btn_layout.addWidget(self.btn_refresh_groups)

        self.btn_remove_group = QPushButton("Remove Selected Group")
        self.btn_remove_group.setStyleSheet("background-color: #f39c12; color: white;")
        apply_shadow_effect(
            self.btn_remove_group, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_remove_group.clicked.connect(self.remove_selected_group)
        groups_btn_layout.addWidget(self.btn_remove_group)
        existing_groups_layout.addLayout(groups_btn_layout)

        self.groups_table = QTableWidget()
        self.groups_table.setColumnCount(1)
        self.groups_table.setHorizontalHeaderLabels(["Group Name"])
        self.groups_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.groups_table.setAlternatingRowColors(True)
        self.groups_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.groups_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.groups_table.setStyleSheet(_TABLE_STYLE)
        self.groups_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.groups_table.setMinimumHeight(200)

        self.groups_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.groups_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.groups_table.customContextMenuRequested.connect(
            self.show_group_context_menu
        )
        self.groups_table.cellPressed.connect(self.store_old_value)
        self.groups_table.itemChanged.connect(self.handle_group_edited)

        existing_groups_layout.addWidget(self.groups_table)
        populate_layout.addWidget(existing_groups_group)


__all__ = ["_UIGroupsMixin"]
