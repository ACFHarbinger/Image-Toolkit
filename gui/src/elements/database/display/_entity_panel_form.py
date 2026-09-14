"""Entity detail panel — form shell: layout build, load/clear, collect/save/delete.

Split from ``entity_detail_panel`` (§5.17 Option B, #629) — pure code
motion, no logic change. Mixed into :class:`_EntityDetailPanel` together
with :mod:`_entity_panel_relations`.
"""

import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from gui.src.components.grouped_tags_display import GroupedTagsDisplay
from gui.src.constants.listings import ENTITY_ROLES, ENTITY_TYPES
from gui.src.elements.database.display.common.base_detail_panel import BaseDetailPanel
from gui.src.styles import apply_shadow_effect
from gui.src.theming.theme_api import qss
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class _EntityPanelFormMixin(BaseDetailPanel):
    """Form shell: widget tree, load/clear/collect, save/delete actions."""

    def __init__(self, parent=None, vault_manager=None):
        super().__init__(parent)
        self.vault_manager = vault_manager
        self._entity_id: Optional[str] = None
        self._credit_data: List[Dict[str, Any]] = []
        self.assoc_content_ids: List[str] = []
        self.assoc_entity_ids: List[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Image preview setup from BaseDetailPanel
        self.img_preview.setFixedSize(160, 160)
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(qss("detail_panel_img_preview_empty"))

        img_row = QHBoxLayout()
        img_row.addWidget(self.img_preview)
        browse_btn = QPushButton("📁 Browse Image")
        browse_btn.clicked.connect(self._browse_image)
        browse_btn.setFixedWidth(130)
        img_row.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignTop)
        img_row.addStretch()
        layout.addLayout(img_row)

        # Form
        form = QFormLayout()
        form.setSpacing(8)

        self.f_name = QLineEdit()
        self.f_name.setPlaceholderText("e.g. Hayao Miyazaki")

        self.f_type = QComboBox()
        self.f_type.addItems(ENTITY_TYPES)

        self.f_role = QComboBox()
        self.f_role.addItems(ENTITY_ROLES)

        self.f_rating = QSpinBox()
        self.f_rating.setRange(0, 10)
        self.f_rating.setSpecialValueText("No rating")

        self.f_year = QSpinBox()
        self.f_year.setRange(0, 2100)
        self.f_year.setValue(0)
        self.f_year.setSpecialValueText("Unknown")

        # Associated Series (linked content entry IDs)
        # QTextEdit (not QLineEdit) so the field can wrap to 2 lines and
        # scroll instead of clipping once the list grows.
        self.f_assoc_content_display = QTextEdit()
        self.f_assoc_content_display.setReadOnly(True)
        self.f_assoc_content_display.setPlaceholderText("None selected")
        self.f_assoc_content_display.setFixedHeight(56)  # ~2 lines of wrapped text
        self.btn_select_content = QPushButton("🎬 Select Content")
        self.btn_select_content.clicked.connect(self._select_associated_content)
        assoc_content_row = QHBoxLayout()
        assoc_content_row.addWidget(self.f_assoc_content_display, 1)
        assoc_content_row.addWidget(self.btn_select_content)

        # Associated Entities (linked entity IDs)
        self.f_assoc_entity_display = QTextEdit()
        self.f_assoc_entity_display.setReadOnly(True)
        self.f_assoc_entity_display.setPlaceholderText("None selected")
        self.f_assoc_entity_display.setFixedHeight(56)  # ~2 lines of wrapped text
        self.btn_select_entities = QPushButton("👥 Select Entities")
        self.btn_select_entities.clicked.connect(self._select_associated_entities)
        assoc_entity_row = QHBoxLayout()
        assoc_entity_row.addWidget(self.f_assoc_entity_display, 1)
        assoc_entity_row.addWidget(self.btn_select_entities)

        self.f_notes = QTextEdit()
        self.f_notes.setPlaceholderText("Biography or notes…")
        self.f_notes.setFixedHeight(100)

        form.addRow("Name *", self.f_name)
        form.addRow("Type", self.f_type)
        form.addRow("Role", self.f_role)
        form.addRow("Rating (0-10)", self.f_rating)
        form.addRow("Debut Year", self.f_year)
        form.addRow("Associated Series", assoc_content_row)
        form.addRow("Associated Entities", assoc_entity_row)
        form.addRow("Biography / Notes", self.f_notes)
        layout.addLayout(form)

        # --- All Tags (grouped by category) Section ---
        # This entity's own tags plus tags carried transitively through
        # associated series (Danbooru-style tag overhaul).
        tags_group = QGroupBox("All Tags (by Category)")
        tags_group.setStyleSheet(qss("detail_panel_group_accent"))
        tags_group_layout = QVBoxLayout(tags_group)

        tags_header_row = QHBoxLayout()
        tags_header_row.addStretch()
        self.btn_add_tag = QPushButton("＋")
        self.btn_add_tag.setToolTip("Add a tag")
        self.btn_add_tag.setFixedWidth(28)
        self.btn_add_tag.clicked.connect(self._on_add_tag)
        tags_header_row.addWidget(self.btn_add_tag)
        tags_group_layout.addLayout(tags_header_row)

        self.grouped_tags_display = GroupedTagsDisplay()
        tags_group_layout.addWidget(self.grouped_tags_display)
        layout.addWidget(tags_group)

        # --- Credit List Section ---
        self.credits_group = QGroupBox("Works / Credits / Appearances")
        self.credits_group.setStyleSheet(qss("detail_panel_group_accent"))
        cg_layout = QVBoxLayout(self.credits_group)

        self.credit_list_layout = QVBoxLayout()
        self.credit_list_layout.setSpacing(4)
        cg_layout.addLayout(self.credit_list_layout)

        add_credit_btn = QPushButton("＋ Add Credit Entry")
        add_credit_btn.clicked.connect(self._add_credit)
        cg_layout.addWidget(add_credit_btn)
        layout.addWidget(self.credits_group)

        # --- Linked Images Section (DB.8b: entity <-> images) ---
        self.linked_images_group = QGroupBox("Linked Images")
        self.linked_images_group.setStyleSheet(qss("detail_panel_group_accent"))
        lig_layout = QVBoxLayout(self.linked_images_group)

        self.linked_images_scroll = QScrollArea()
        self.linked_images_scroll.setWidgetResizable(True)
        self.linked_images_scroll.setFixedHeight(90)
        self.linked_images_scroll.setStyleSheet(qss("scroll_area_borderless"))
        self.linked_images_container = QWidget()
        self.linked_images_layout = QHBoxLayout(self.linked_images_container)
        self.linked_images_layout.setContentsMargins(0, 0, 0, 0)
        self.linked_images_layout.setSpacing(6)
        self.linked_images_layout.addStretch()
        self.linked_images_scroll.setWidget(self.linked_images_container)
        lig_layout.addWidget(self.linked_images_scroll)

        add_linked_image_btn = QPushButton("➕ Link Image…")
        add_linked_image_btn.clicked.connect(self._link_image)
        lig_layout.addWidget(add_linked_image_btn)
        layout.addWidget(self.linked_images_group)

        # Action buttons
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setStyleSheet(qss("shared_button"))
        self.save_btn.clicked.connect(self._on_save)
        apply_shadow_effect(self.save_btn)

        self.del_btn = QPushButton("🗑 Delete")
        self.del_btn.setStyleSheet(qss("detail_panel_delete_btn"))
        self.del_btn.clicked.connect(self._on_delete)
        apply_shadow_effect(self.del_btn)

        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.del_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

    def load_entity(self, entity: Dict[str, Any]):
        self._entity_id = entity.get("id")
        self._image_path = entity.get("image_path", "")
        self.f_name.setText(entity.get("name", ""))
        self.f_type.setCurrentText(entity.get("type", "Person"))
        self.f_role.setCurrentText(entity.get("role", "Director"))
        self.f_rating.setValue(entity.get("rating", 0))
        self.f_year.setValue(entity.get("year", 0))
        self.f_notes.setPlainText(entity.get("notes", ""))
        self._credit_data = entity.get("credit_list", [])

        # Handle both legacy string format and new list-of-IDs format
        raw_content = entity.get("associated_content", [])
        self.assoc_content_ids = raw_content if isinstance(raw_content, list) else []

        raw_entities = entity.get("associated_entities", [])
        self.assoc_entity_ids = raw_entities if isinstance(raw_entities, list) else []

        self.del_btn.setVisible(True)
        self.credits_group.setVisible(True)
        self.linked_images_group.setVisible(True)
        QTimer.singleShot(0, self._refresh_assoc_displays)
        QTimer.singleShot(0, self._refresh_image)
        QTimer.singleShot(0, self._refresh_credit_list)
        QTimer.singleShot(0, self._refresh_linked_images)
        QTimer.singleShot(0, self._refresh_grouped_tags_display)

    def clear_for_new(self):
        self._entity_id = None
        self._image_path = ""
        self._credit_data = []
        self.assoc_content_ids = []
        self.assoc_entity_ids = []
        self.f_name.clear()
        self.f_type.setCurrentIndex(0)
        self.f_role.setCurrentIndex(0)
        self.f_rating.setValue(0)
        self.f_year.setValue(0)
        self.f_assoc_content_display.clear()
        self.f_assoc_entity_display.clear()
        self.f_notes.clear()
        self.grouped_tags_display.set_grouped_tags({})
        self.img_preview.clear()
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(qss("detail_panel_img_preview_empty"))
        self._refresh_credit_list()
        self._refresh_linked_images()
        self.del_btn.setVisible(False)
        self.credits_group.setVisible(False)
        self.linked_images_group.setVisible(False)

    def _browse_image(self):
        self._image_path = self._browse_image_helper(self._entity_id) # pyrefly: ignore [bad-argument-type]

    def _collect(self) -> Optional[Dict[str, Any]]:
        name = self.f_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a name.")
            return None
        return {
            "id": self._entity_id or str(uuid.uuid4()),
            "name": name,
            "type": self.f_type.currentText(),
            "role": self.f_role.currentText(),
            "rating": self.f_rating.value(),
            "year": self.f_year.value(),
            "associated_content": list(self.assoc_content_ids),
            "associated_entities": list(self.assoc_entity_ids),
            "notes": self.f_notes.toPlainText().strip(),
            "image_path": self._image_path,
            "credit_list": self._credit_data,
            "date_added": str(date.today()),
        }

    @Slot()
    def _on_save(self):
        entity = self._collect()
        if entity:
            self.saved.emit(entity)

    @Slot()
    def _on_delete(self):
        if not self._entity_id:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Permanently remove this entity from your listings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.deleted.emit(self._entity_id)


__all__ = ["_EntityPanelFormMixin"]
