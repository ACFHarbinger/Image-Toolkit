"""Subgroup-management UI section builder for ``DatabaseTab``.

Extracted from ``DatabaseTab.__init__`` -- pure code motion, no logic change
(see ``_ui_connection.py``'s docstring). Assumes ``self.groups_table`` already
exists (``_build_groups_section`` runs first) -- its stylesheet is reused for
visual consistency, matching the original inline code.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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


class _UISubgroupsMixin:
    """Builds the create-subgroup and existing-subgroups sections."""

    def _build_subgroups_section(self, populate_layout) -> None:
        # --- Create New Subgroup section ---
        create_subgroup_group = QGroupBox("Create Subgroup(s)")
        create_subgroup_layout = QFormLayout(create_subgroup_group)

        self.new_subgroup_parent_combo = QComboBox()
        self.new_subgroup_parent_combo.setPlaceholderText("Select Parent Group...")
        self.new_subgroup_parent_combo.setEditable(True)
        create_subgroup_layout.addRow("Parent Group:", self.new_subgroup_parent_combo)

        self.new_subgroup_name_edit = QLineEdit()
        self.new_subgroup_name_edit.setPlaceholderText(
            "subgroup1, subgroup2 ... (comma-separated)"
        )
        create_subgroup_layout.addRow("Subgroup Name(s):", self.new_subgroup_name_edit)

        self.btn_create_subgroup = QPushButton("Create Subgroup(s)")
        apply_shadow_effect(
            self.btn_create_subgroup,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.btn_create_subgroup.clicked.connect(self.create_new_subgroup)
        create_subgroup_layout.addRow(self.btn_create_subgroup)

        self.new_subgroup_name_edit.returnPressed.connect(
            self.btn_create_subgroup.click
        )
        populate_layout.addWidget(create_subgroup_group)

        # --- Existing Subgroups section ---
        existing_subgroups_group = QGroupBox("Existing Subgroups")
        existing_subgroups_layout = QVBoxLayout(existing_subgroups_group)

        existing_subgroups_filter_layout = QHBoxLayout()
        existing_subgroups_filter_layout.addWidget(QLabel("Filter by Group:"))
        self.existing_subgroups_filter_combo = QComboBox()
        self.existing_subgroups_filter_combo.setPlaceholderText(
            "Select Group to View..."
        )
        existing_subgroups_filter_layout.addWidget(self.existing_subgroups_filter_combo)
        existing_subgroups_layout.addLayout(existing_subgroups_filter_layout)

        self.existing_subgroups_filter_combo.currentTextChanged.connect(
            self.refresh_subgroups_list
        )

        subgroups_btn_layout = QHBoxLayout()
        self.btn_refresh_subgroups = QPushButton("Refresh Group Filters")
        apply_shadow_effect(
            self.btn_refresh_subgroups,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.btn_refresh_subgroups.clicked.connect(self._refresh_all_group_combos)
        subgroups_btn_layout.addWidget(self.btn_refresh_subgroups)

        self.btn_remove_subgroup = QPushButton("Remove Selected Subgroup")
        self.btn_remove_subgroup.setObjectName("btn_danger")
        apply_shadow_effect(
            self.btn_remove_subgroup,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.btn_remove_subgroup.clicked.connect(self.remove_selected_subgroup)
        subgroups_btn_layout.addWidget(self.btn_remove_subgroup)
        existing_subgroups_layout.addLayout(subgroups_btn_layout)

        self.subgroups_table = QTableWidget()
        self.subgroups_table.setColumnCount(2)
        self.subgroups_table.setHorizontalHeaderLabels(
            ["Subgroup Name", "Parent Group"]
        )
        self.subgroups_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.subgroups_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.subgroups_table.setAlternatingRowColors(True)
        self.subgroups_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.subgroups_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.subgroups_table.setStyleSheet(self.groups_table.styleSheet())
        self.subgroups_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.subgroups_table.setMinimumHeight(200)

        self.subgroups_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
        )
        self.subgroups_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.subgroups_table.customContextMenuRequested.connect(
            self.show_subgroup_context_menu
        )
        self.subgroups_table.cellPressed.connect(self.store_old_value)
        self.subgroups_table.itemChanged.connect(self.handle_subgroup_edited)

        existing_subgroups_layout.addWidget(self.subgroups_table)
        populate_layout.addWidget(existing_subgroups_group)


__all__ = ["_UISubgroupsMixin"]
