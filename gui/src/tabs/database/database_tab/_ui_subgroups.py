"""Subgroup-management UI section builder for ``DatabaseTab`` (§5.17, #544)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    pass


def build_subgroups_section(tab: Any, populate_layout: QVBoxLayout) -> None:
    """Build create-subgroup and existing-subgroups sections onto tab."""
    # --- Create New Subgroup section ---
    create_subgroup_group = QGroupBox("Create Subgroup(s)")
    create_subgroup_layout = QFormLayout(create_subgroup_group)

    tab.new_subgroup_parent_combo = QComboBox()
    tab.new_subgroup_parent_combo.setPlaceholderText("Select Parent Group...")
    tab.new_subgroup_parent_combo.setEditable(True)
    create_subgroup_layout.addRow("Parent Group:", tab.new_subgroup_parent_combo)

    tab.new_subgroup_name_edit = QLineEdit()
    tab.new_subgroup_name_edit.setPlaceholderText(
        "subgroup1, subgroup2 ... (comma-separated)"
    )
    create_subgroup_layout.addRow("Subgroup Name(s):", tab.new_subgroup_name_edit)

    tab.btn_create_subgroup = QPushButton("Create Subgroup(s)")
    apply_shadow_effect(
        tab.btn_create_subgroup,
        color_hex="#000000",
        radius=8,
        x_offset=0,
        y_offset=3,
    )
    tab.btn_create_subgroup.clicked.connect(tab.create_new_subgroup)
    create_subgroup_layout.addRow(tab.btn_create_subgroup)

    tab.new_subgroup_name_edit.returnPressed.connect(
        tab.btn_create_subgroup.click
    )
    populate_layout.addWidget(create_subgroup_group)

    # --- Existing Subgroups section ---
    existing_subgroups_group = QGroupBox("Existing Subgroups")
    existing_subgroups_layout = QVBoxLayout(existing_subgroups_group)

    existing_subgroups_filter_layout = QHBoxLayout()
    existing_subgroups_filter_layout.addWidget(QLabel("Filter by Group:"))
    tab.existing_subgroups_filter_combo = QComboBox()
    tab.existing_subgroups_filter_combo.setPlaceholderText(
        "Select Group to View..."
    )
    existing_subgroups_filter_layout.addWidget(tab.existing_subgroups_filter_combo)
    existing_subgroups_layout.addLayout(existing_subgroups_filter_layout)

    tab.existing_subgroups_filter_combo.currentTextChanged.connect(
        tab.refresh_subgroups_list
    )

    subgroups_btn_layout = QHBoxLayout()
    tab.btn_refresh_subgroups = QPushButton("Refresh Group Filters")
    apply_shadow_effect(
        tab.btn_refresh_subgroups,
        color_hex="#000000",
        radius=8,
        x_offset=0,
        y_offset=3,
    )
    tab.btn_refresh_subgroups.clicked.connect(tab._refresh_all_group_combos)
    subgroups_btn_layout.addWidget(tab.btn_refresh_subgroups)

    tab.btn_remove_subgroup = QPushButton("Remove Selected Subgroup")
    tab.btn_remove_subgroup.setObjectName("btn_danger")
    apply_shadow_effect(
        tab.btn_remove_subgroup,
        color_hex="#000000",
        radius=8,
        x_offset=0,
        y_offset=3,
    )
    tab.btn_remove_subgroup.clicked.connect(tab.remove_selected_subgroup)
    subgroups_btn_layout.addWidget(tab.btn_remove_subgroup)
    existing_subgroups_layout.addLayout(subgroups_btn_layout)

    tab.subgroups_table = QTableWidget()
    tab.subgroups_table.setColumnCount(2)
    tab.subgroups_table.setHorizontalHeaderLabels(
        ["Subgroup Name", "Parent Group"]
    )
    tab.subgroups_table.horizontalHeader().setSectionResizeMode(
        0, QHeaderView.ResizeMode.Stretch
    )
    tab.subgroups_table.horizontalHeader().setSectionResizeMode(
        1, QHeaderView.ResizeMode.Stretch
    )
    tab.subgroups_table.setAlternatingRowColors(True)
    tab.subgroups_table.setSelectionBehavior(
        QAbstractItemView.SelectionBehavior.SelectRows
    )
    tab.subgroups_table.setSelectionMode(
        QAbstractItemView.SelectionMode.SingleSelection
    )
    tab.subgroups_table.setStyleSheet(tab.groups_table.styleSheet())
    tab.subgroups_table.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    tab.subgroups_table.setMinimumHeight(200)

    tab.subgroups_table.setEditTriggers(
        QAbstractItemView.EditTrigger.DoubleClicked
    )
    tab.subgroups_table.setContextMenuPolicy(
        Qt.ContextMenuPolicy.CustomContextMenu
    )
    tab.subgroups_table.customContextMenuRequested.connect(
        tab.show_subgroup_context_menu
    )
    tab.subgroups_table.cellPressed.connect(tab.store_old_value)
    tab.subgroups_table.itemChanged.connect(tab.handle_subgroup_edited)

    existing_subgroups_layout.addWidget(tab.subgroups_table)
    populate_layout.addWidget(existing_subgroups_group)


class DatabaseSubgroupsUIBuilder:
    """Builder for the subgroups section."""

    def __init__(self, tab: Any) -> None:
        self.tab = tab

    def build(self, populate_layout: QVBoxLayout) -> None:
        build_subgroups_section(self.tab, populate_layout)


class _UISubgroupsMixin:
    """Backward-compatible mixin adapter."""

    def _build_subgroups_section(self, populate_layout: QVBoxLayout) -> None:
        build_subgroups_section(self, populate_layout)


__all__ = ["DatabaseSubgroupsUIBuilder", "_UISubgroupsMixin", "build_subgroups_section"]
