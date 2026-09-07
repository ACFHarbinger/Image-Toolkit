"""Tag-management UI section builder for ``DatabaseTab`` (§5.17, #544)."""

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
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
)

from ....styles import apply_shadow_effect

if TYPE_CHECKING:
    pass


def build_tags_section(tab: Any, populate_layout: QVBoxLayout) -> None:
    """Build create-tag, bulk-import, and existing-tags sections onto tab."""
    # --- Create New Tag section ---
    create_tag_group = QGroupBox("Create/Update Tag(s)")
    create_tag_layout = QFormLayout(create_tag_group)

    tab.new_tag_name_edit = QLineEdit()
    tab.new_tag_name_edit.setPlaceholderText(
        "tag1, tag2, tag3 ... (comma-separated)"
    )
    create_tag_layout.addRow("Tag Name(s):", tab.new_tag_name_edit)

    tab.new_tag_type_combo = QComboBox()
    tab.new_tag_type_combo.setEditable(True)
    tab.new_tag_type_combo.addItems(
        ["", "Artist", "Copyright", "Character", "General", "Meta"]
    )
    tab.new_tag_type_combo.setPlaceholderText(
        "e.g., Artist, Character, General (Optional)"
    )
    create_tag_layout.addRow("Tag Category (applies to all):", tab.new_tag_type_combo)

    tab.btn_create_tag = QPushButton("Create/Update Tag(s)")
    apply_shadow_effect(
        tab.btn_create_tag, color_hex="#000000", radius=8, x_offset=0, y_offset=3
    )
    tab.btn_create_tag.clicked.connect(tab.create_new_tag)
    create_tag_layout.addRow(tab.btn_create_tag)

    tab.new_tag_name_edit.returnPressed.connect(tab.btn_create_tag.click)
    tab.new_tag_type_combo.lineEdit().returnPressed.connect(  # pyrefly: ignore [missing-attribute]
        tab.btn_create_tag.click
    )

    populate_layout.addWidget(create_tag_group)

    # -------------------------------------------------------------
    # Bulk Tag Import Section
    # -------------------------------------------------------------
    bulk_import_group = QGroupBox("Bulk Tag Import from JSON")
    bulk_import_layout = QFormLayout(bulk_import_group)

    tab.bulk_tag_type_combo = QComboBox()
    tab.bulk_tag_type_combo.setEditable(True)
    tab.bulk_tag_type_combo.addItems(
        ["", "Artist", "Copyright", "Character", "General", "Meta"]
    )
    tab.bulk_tag_type_combo.setPlaceholderText("Tag Category to apply (e.g., Artist)")
    bulk_import_layout.addRow("Tag Category:", tab.bulk_tag_type_combo)

    tab.json_file_path_edit = QLineEdit()
    tab.json_file_path_edit.setPlaceholderText(
        "Select JSON file containing a 'tags' array..."
    )

    btn_browse_json = QPushButton("Browse JSON")
    btn_browse_json.clicked.connect(tab.browse_json_file)

    json_h_layout = QHBoxLayout()
    json_h_layout.addWidget(tab.json_file_path_edit)
    json_h_layout.addWidget(btn_browse_json)
    bulk_import_layout.addRow("JSON File:", json_h_layout)

    tab.btn_import_tags = QPushButton("Import Tags from JSON")
    apply_shadow_effect(
        tab.btn_import_tags, color_hex="#000000", radius=8, x_offset=0, y_offset=3
    )
    tab.btn_import_tags.clicked.connect(tab.import_tags_from_json)
    bulk_import_layout.addRow(tab.btn_import_tags)

    populate_layout.addWidget(bulk_import_group)
    # -------------------------------------------------------------

    # --- Existing Tags section ---
    existing_tags_group = QGroupBox("Existing Tags")
    existing_tags_layout = QVBoxLayout(existing_tags_group)

    tags_btn_layout = QHBoxLayout()
    tab.btn_refresh_tags = QPushButton("Refresh List")
    apply_shadow_effect(
        tab.btn_refresh_tags, color_hex="#000000", radius=8, x_offset=0, y_offset=3
    )
    tab.btn_refresh_tags.clicked.connect(tab.refresh_tags_list)
    tags_btn_layout.addWidget(tab.btn_refresh_tags)

    tab.btn_remove_tag = QPushButton("Remove Selected Tag")
    tab.btn_remove_tag.setObjectName("btn_danger")
    apply_shadow_effect(
        tab.btn_remove_tag, color_hex="#000000", radius=8, x_offset=0, y_offset=3
    )
    tab.btn_remove_tag.clicked.connect(tab.remove_selected_tag)
    tags_btn_layout.addWidget(tab.btn_remove_tag)
    existing_tags_layout.addLayout(tags_btn_layout)

    tab.tags_table = QTableWidget()
    tab.tags_table.setColumnCount(2)
    tab.tags_table.setHorizontalHeaderLabels(["Tag Name", "Tag Category"])
    tab.tags_table.horizontalHeader().setSectionResizeMode(
        0, QHeaderView.ResizeMode.Stretch
    )
    tab.tags_table.horizontalHeader().setSectionResizeMode(
        1, QHeaderView.ResizeMode.Stretch
    )
    tab.tags_table.setAlternatingRowColors(True)
    tab.tags_table.setSelectionBehavior(
        QAbstractItemView.SelectionBehavior.SelectRows
    )
    tab.tags_table.setSelectionMode(
        QAbstractItemView.SelectionMode.SingleSelection
    )
    tab.tags_table.setStyleSheet(tab.groups_table.styleSheet())
    tab.tags_table.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    tab.tags_table.setMinimumHeight(200)

    tab.tags_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
    tab.tags_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tab.tags_table.customContextMenuRequested.connect(tab.show_tag_context_menu)
    tab.tags_table.cellPressed.connect(tab.store_old_value)
    tab.tags_table.itemChanged.connect(tab.handle_tag_edited)

    existing_tags_layout.addWidget(tab.tags_table)
    populate_layout.addWidget(existing_tags_group)


class DatabaseTagsUIBuilder:
    """Builder for the tags section."""

    def __init__(self, tab: Any) -> None:
        self.tab = tab

    def build(self, populate_layout: QVBoxLayout) -> None:
        build_tags_section(self.tab, populate_layout)


class _UITagsMixin:
    """Backward-compatible mixin adapter."""

    def _build_tags_section(self, populate_layout: QVBoxLayout) -> None:
        build_tags_section(self, populate_layout)


__all__ = ["DatabaseTagsUIBuilder", "_UITagsMixin", "build_tags_section"]
