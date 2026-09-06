"""Group-management UI section builder for ``DatabaseTab`` (§5.17, #544)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

from gui.src.constants.elements import _TABLE_STYLE

from ....styles import apply_shadow_effect

if TYPE_CHECKING:
    pass


def build_groups_section(tab: Any, populate_layout: QVBoxLayout) -> None:
    """Build auto-populate, create-group, and existing-groups sections onto tab."""
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

    tab.btn_auto_populate = QPushButton(
        "Auto-Sync Groups and Subgroups from Source"
    )
    tab.btn_auto_populate.setObjectName("btn_success")
    apply_shadow_effect(
        tab.btn_auto_populate,
        color_hex="#000000",
        radius=8,
        x_offset=0,
        y_offset=3,
    )
    tab.btn_auto_populate.clicked.connect(tab.auto_populate_from_source)
    auto_pop_layout.addWidget(tab.btn_auto_populate)

    populate_layout.addWidget(auto_pop_group)
    # -------------------------------------------------------------

    # --- Create New Group section ---
    create_group_group = QGroupBox("Create Group(s)")
    create_group_layout = QFormLayout(create_group_group)

    tab.new_group_name_edit = QLineEdit()
    tab.new_group_name_edit.setPlaceholderText(
        "group1, group2, group3 ... (comma-separated)"
    )
    create_group_layout.addRow("Group Name(s):", tab.new_group_name_edit)

    tab.btn_create_group = QPushButton("Create Group(s)")
    apply_shadow_effect(
        tab.btn_create_group, color_hex="#000000", radius=8, x_offset=0, y_offset=3
    )
    tab.btn_create_group.clicked.connect(tab.create_new_group)
    create_group_layout.addRow(tab.btn_create_group)

    tab.new_group_name_edit.returnPressed.connect(tab.btn_create_group.click)
    populate_layout.addWidget(create_group_group)

    # --- Existing Groups section ---
    existing_groups_group = QGroupBox("Existing Groups")
    existing_groups_layout = QVBoxLayout(existing_groups_group)

    groups_btn_layout = QHBoxLayout()
    tab.btn_refresh_groups = QPushButton("Refresh List")
    apply_shadow_effect(
        tab.btn_refresh_groups,
        color_hex="#000000",
        radius=8,
        x_offset=0,
        y_offset=3,
    )
    tab.btn_refresh_groups.clicked.connect(tab.refresh_groups_list)
    groups_btn_layout.addWidget(tab.btn_refresh_groups)

    tab.btn_remove_group = QPushButton("Remove Selected Group")
    tab.btn_remove_group.setObjectName("btn_danger")
    apply_shadow_effect(
        tab.btn_remove_group, color_hex="#000000", radius=8, x_offset=0, y_offset=3
    )
    tab.btn_remove_group.clicked.connect(tab.remove_selected_group)
    groups_btn_layout.addWidget(tab.btn_remove_group)
    existing_groups_layout.addLayout(groups_btn_layout)

    tab.groups_table = QTableWidget()
    tab.groups_table.setColumnCount(1)
    tab.groups_table.setHorizontalHeaderLabels(["Group Name"])
    tab.groups_table.horizontalHeader().setSectionResizeMode(
        0, QHeaderView.ResizeMode.Stretch
    )
    tab.groups_table.setAlternatingRowColors(True)
    tab.groups_table.setSelectionBehavior(
        QAbstractItemView.SelectionBehavior.SelectRows
    )
    tab.groups_table.setSelectionMode(
        QAbstractItemView.SelectionMode.SingleSelection
    )
    tab.groups_table.setStyleSheet(_TABLE_STYLE)
    tab.groups_table.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    tab.groups_table.setMinimumHeight(200)

    tab.groups_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
    tab.groups_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tab.groups_table.customContextMenuRequested.connect(
        tab.show_group_context_menu
    )
    tab.groups_table.cellPressed.connect(tab.store_old_value)
    tab.groups_table.itemChanged.connect(tab.handle_group_edited)

    existing_groups_layout.addWidget(tab.groups_table)
    populate_layout.addWidget(existing_groups_group)


class DatabaseGroupsUIBuilder:
    """Builder for the groups section."""

    def __init__(self, tab: Any) -> None:
        self.tab = tab

    def build(self, populate_layout: QVBoxLayout) -> None:
        build_groups_section(self.tab, populate_layout)


class _UIGroupsMixin:
    """Backward-compatible mixin adapter."""

    def _build_groups_section(self, populate_layout: QVBoxLayout) -> None:
        build_groups_section(self, populate_layout)


__all__ = ["DatabaseGroupsUIBuilder", "_UIGroupsMixin", "build_groups_section"]
