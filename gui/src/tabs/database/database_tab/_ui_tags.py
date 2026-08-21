"""Tag-management UI section builder for ``DatabaseTab``.

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
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
)

from ....styles import apply_shadow_effect


class _UITagsMixin:
    """Builds the create-tag, bulk-import, and existing-tags sections."""

    def _build_tags_section(self, populate_layout) -> None:
        # --- Create New Tag section ---
        create_tag_group = QGroupBox("Create/Update Tag(s)")
        create_tag_layout = QFormLayout(create_tag_group)

        self.new_tag_name_edit = QLineEdit()
        self.new_tag_name_edit.setPlaceholderText(
            "tag1, tag2, tag3 ... (comma-separated)"
        )
        create_tag_layout.addRow("Tag Name(s):", self.new_tag_name_edit)

        self.new_tag_type_combo = QComboBox()
        self.new_tag_type_combo.setEditable(True)
        self.new_tag_type_combo.addItems(
            ["", "Artist", "Copyright", "Character", "General", "Meta"]
        )
        self.new_tag_type_combo.setPlaceholderText(
            "e.g., Artist, Character, General (Optional)"
        )
        create_tag_layout.addRow("Tag Category (applies to all):", self.new_tag_type_combo)

        self.btn_create_tag = QPushButton("Create/Update Tag(s)")
        apply_shadow_effect(
            self.btn_create_tag, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_create_tag.clicked.connect(self.create_new_tag)
        create_tag_layout.addRow(self.btn_create_tag)

        self.new_tag_name_edit.returnPressed.connect(self.btn_create_tag.click)
        self.new_tag_type_combo.lineEdit().returnPressed.connect(  # pyrefly: ignore [missing-attribute]
            self.btn_create_tag.click
        )

        populate_layout.addWidget(create_tag_group)

        # -------------------------------------------------------------
        # Bulk Tag Import Section
        # -------------------------------------------------------------
        bulk_import_group = QGroupBox("Bulk Tag Import from JSON")
        bulk_import_layout = QFormLayout(bulk_import_group)

        self.bulk_tag_type_combo = QComboBox()
        self.bulk_tag_type_combo.setEditable(True)
        self.bulk_tag_type_combo.addItems(
            ["", "Artist", "Copyright", "Character", "General", "Meta"]
        )
        self.bulk_tag_type_combo.setPlaceholderText("Tag Category to apply (e.g., Artist)")
        bulk_import_layout.addRow("Tag Category:", self.bulk_tag_type_combo)

        self.json_file_path_edit = QLineEdit()
        self.json_file_path_edit.setPlaceholderText(
            "Select JSON file containing a 'tags' array..."
        )

        btn_browse_json = QPushButton("Browse JSON")
        btn_browse_json.clicked.connect(self.browse_json_file)

        json_h_layout = QHBoxLayout()
        json_h_layout.addWidget(self.json_file_path_edit)
        json_h_layout.addWidget(btn_browse_json)
        bulk_import_layout.addRow("JSON File:", json_h_layout)

        self.btn_import_tags = QPushButton("Import Tags from JSON")
        apply_shadow_effect(
            self.btn_import_tags, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_import_tags.clicked.connect(self.import_tags_from_json)
        bulk_import_layout.addRow(self.btn_import_tags)

        populate_layout.addWidget(bulk_import_group)
        # -------------------------------------------------------------

        # --- Existing Tags section ---
        existing_tags_group = QGroupBox("Existing Tags")
        existing_tags_layout = QVBoxLayout(existing_tags_group)

        tags_btn_layout = QHBoxLayout()
        self.btn_refresh_tags = QPushButton("Refresh List")
        apply_shadow_effect(
            self.btn_refresh_tags, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_refresh_tags.clicked.connect(self.refresh_tags_list)
        tags_btn_layout.addWidget(self.btn_refresh_tags)

        self.btn_remove_tag = QPushButton("Remove Selected Tag")
        self.btn_remove_tag.setObjectName("btn_danger")
        apply_shadow_effect(
            self.btn_remove_tag, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_remove_tag.clicked.connect(self.remove_selected_tag)
        tags_btn_layout.addWidget(self.btn_remove_tag)
        existing_tags_layout.addLayout(tags_btn_layout)

        self.tags_table = QTableWidget()
        self.tags_table.setColumnCount(2)
        self.tags_table.setHorizontalHeaderLabels(["Tag Name", "Tag Category"])
        self.tags_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.tags_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.tags_table.setAlternatingRowColors(True)
        self.tags_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tags_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tags_table.setStyleSheet(self.groups_table.styleSheet())
        self.tags_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.tags_table.setMinimumHeight(200)

        self.tags_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.tags_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tags_table.customContextMenuRequested.connect(self.show_tag_context_menu)
        self.tags_table.cellPressed.connect(self.store_old_value)
        self.tags_table.itemChanged.connect(self.handle_tag_edited)

        existing_tags_layout.addWidget(self.tags_table)
        populate_layout.addWidget(existing_tags_group)


__all__ = ["_UITagsMixin"]
