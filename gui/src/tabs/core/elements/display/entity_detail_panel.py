import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import base
from backend.src.constants import IMAGE_TOOLKIT_DIR
from gui.src.constants.listings import (
    ENTITY_ROLES,
    ENTITY_TYPES,
)
from gui.src.helpers.image import (
    _CARD_THUMB_CACHE,
    _ThumbWorker,
)
from gui.src.styles import SHARED_BUTTON_STYLE, apply_shadow_effect
from gui.src.tabs.core.elements.dialog import (
    _AssociatedContentDialog,
    _AssociatedEntitiesDialog,
)
from gui.src.tabs.core.elements.dialog.credit_dialog import _CreditDialog
from gui.src.tabs.core.elements.display.common.base_detail_panel import BaseDetailPanel
from PySide6.QtCore import Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)


class _EntityDetailPanel(BaseDetailPanel):
    saved = Signal(dict)
    deleted = Signal(str)

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
        self.img_preview.setStyleSheet(
            "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
        )

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

        # Associated Content (linked content entry IDs)
        self.f_assoc_content_display = QLineEdit()
        self.f_assoc_content_display.setReadOnly(True)
        self.f_assoc_content_display.setPlaceholderText("None selected")
        self.btn_select_content = QPushButton("🎬 Select Content")
        self.btn_select_content.clicked.connect(self._select_associated_content)
        assoc_content_row = QHBoxLayout()
        assoc_content_row.addWidget(self.f_assoc_content_display, 1)
        assoc_content_row.addWidget(self.btn_select_content)

        # Associated Entities (linked entity IDs)
        self.f_assoc_entity_display = QLineEdit()
        self.f_assoc_entity_display.setReadOnly(True)
        self.f_assoc_entity_display.setPlaceholderText("None selected")
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
        form.addRow("Associated Content", assoc_content_row)
        form.addRow("Associated Entities", assoc_entity_row)
        form.addRow("Biography / Notes", self.f_notes)
        layout.addLayout(form)

        # --- Credit List Section ---
        self.credits_group = QGroupBox("Works / Credits / Appearances")
        self.credits_group.setStyleSheet("QGroupBox{font-weight:bold; color:#00bcd4;}")
        cg_layout = QVBoxLayout(self.credits_group)

        self.credit_list_layout = QVBoxLayout()
        self.credit_list_layout.setSpacing(4)
        cg_layout.addLayout(self.credit_list_layout)

        add_credit_btn = QPushButton("＋ Add Credit Entry")
        add_credit_btn.clicked.connect(self._add_credit)
        cg_layout.addWidget(add_credit_btn)
        layout.addWidget(self.credits_group)

        # Action buttons
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        self.save_btn.clicked.connect(self._on_save)
        apply_shadow_effect(self.save_btn)

        self.del_btn = QPushButton("🗑 Delete")
        self.del_btn.setStyleSheet(
            "QPushButton{background:#c0392b;color:white;font-weight:bold;"
            "padding:10px;border-radius:8px;}"
            "QPushButton:hover{background:#e74c3c;}"
        )
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
        QTimer.singleShot(0, self._refresh_assoc_displays)
        QTimer.singleShot(0, self._refresh_image)
        QTimer.singleShot(0, self._refresh_credit_list)

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
        self.img_preview.clear()
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(
            "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
        )
        self._refresh_credit_list()
        self.del_btn.setVisible(False)
        self.credits_group.setVisible(False)

    def _browse_image(self):
        self._image_path = self._browse_image_helper(self._entity_id) # pyrefly: ignore [bad-argument-type]

    def _refresh_credit_list(self):
        while self.credit_list_layout.count():
            item = self.credit_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater() # pyrefly: ignore [missing-attribute]

        sorted_credits = sorted(
            self._credit_data, key=lambda x: x.get("year", 0), reverse=True
        )

        for cr in sorted_credits:
            row = QFrame()
            row.setStyleSheet(
                "QFrame{background:#23272a; border-radius:4px; padding:2px;}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(6, 4, 6, 4)

            title = cr.get("title", "Untitled")
            role = cr.get("role", "")
            year = cr.get("year", 0)
            rating = cr.get("rating", 0)
            img_path = cr.get("image_path", "")

            t_lbl = QLabel()
            t_lbl.setFixedSize(50, 40)
            t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            t_lbl.setStyleSheet("background:#1a1c1e; border-radius:3px;")
            if img_path and Path(img_path).exists():
                cached = _CARD_THUMB_CACHE.get(img_path)
                if cached is not None:
                    t_lbl.setPixmap(
                        QPixmap.fromImage(cached).scaled(
                            50,
                            40,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                else:

                    def _set_cr_thumb(p: str, img: QImage, lbl=t_lbl) -> None:
                        if lbl and not lbl.pixmap():
                            lbl.setPixmap(
                                QPixmap.fromImage(img).scaled(
                                    50,
                                    40,
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation,
                                )
                            )

                    w = _ThumbWorker(img_path, 80)
                    w.signals.ready.connect(_set_cr_thumb)
                    QThreadPool.globalInstance().start(w)
            else:
                t_lbl.setText("No Img")
                t_lbl.setStyleSheet(
                    "background:#1a1c1e; border-radius:3px; color:#555; font-size:8px;"
                )
            rl.addWidget(t_lbl)

            role_part = f" as <i>{role}</i>" if role else ""
            year_part = f" ({year})" if year else ""
            info = QLabel(f"<b>{title}</b>{role_part}{year_part}")
            rl.addWidget(info, 1)
            if rating:
                r_lbl = QLabel("★" * rating)
                r_lbl.setStyleSheet("color:#f1c40f; font-size:10px;")
                rl.addWidget(r_lbl)

            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(24, 24)
            edit_btn.setToolTip("Edit credit")
            edit_btn.clicked.connect(lambda _, c=cr: self._edit_credit(c))
            rl.addWidget(edit_btn)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(24, 24)
            del_btn.setToolTip("Remove credit record")
            del_btn.clicked.connect(lambda _, cid=cr["id"]: self._remove_credit(cid))
            rl.addWidget(del_btn)

            self.credit_list_layout.addWidget(row)

    def _add_credit(self):
        dlg = _CreditDialog(parent=self)
        if dlg.exec():
            new_cr = dlg.get_data()
            self._credit_data.append(new_cr)
            self._refresh_credit_list()

    def _edit_credit(self, credit_data: Dict[str, Any]):
        dlg = _CreditDialog(credit_data, parent=self)
        if dlg.exec():
            updated = dlg.get_data()
            for i, c in enumerate(self._credit_data):
                if c["id"] == updated["id"]:
                    self._credit_data[i] = updated
                    break
            self._refresh_credit_list()

    def _remove_credit(self, credit_id: str):
        self._credit_data = [c for c in self._credit_data if c["id"] != credit_id]
        self._refresh_credit_list()

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

    def _refresh_assoc_displays(self) -> None:
        db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
        if (
            not self.vault_manager
            or not hasattr(self.vault_manager, "raw_password")
            or not self.vault_manager.raw_password
        ):
            self.f_assoc_content_display.setText("None selected")
            self.f_assoc_entity_display.setText("None selected")
            return

        password = self.vault_manager.raw_password
        salt = self.vault_manager.account_name

        try:
            rows = base.fetch_all_listings_secure(db_path, password, salt) # pyrefly: ignore [missing-attribute]

            title_map = {}
            name_map = {}
            for row in rows:
                id_, category, title, _, _ = row
                if category == "Entity":
                    name_map[id_] = title
                else:
                    title_map[id_] = title

            content_names = [title_map.get(i, i) for i in self.assoc_content_ids]
            self.f_assoc_content_display.setText(", ".join(content_names))

            entity_names = [name_map.get(i, i) for i in self.assoc_entity_ids]
            self.f_assoc_entity_display.setText(", ".join(entity_names))
        except Exception as e:
            print(f"Failed to refresh assoc displays: {e}")
            self.f_assoc_content_display.setText(
                f"{len(self.assoc_content_ids)} linked"
            )
            self.f_assoc_entity_display.setText(f"{len(self.assoc_entity_ids)} linked")

    def _select_associated_content(self) -> None:
        entries = []
        if (
            self.vault_manager
            and hasattr(self.vault_manager, "raw_password")
            and self.vault_manager.raw_password
        ):
            db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
            password = self.vault_manager.raw_password
            salt = self.vault_manager.account_name
            try:
                rows = base.fetch_all_listings_secure(db_path, password, salt) # pyrefly: ignore [missing-attribute]
                for row in rows:
                    id_, category, title, metadata_json, date_added = row
                    if category != "Entity":
                        try:
                            entry = json.loads(metadata_json)
                        except Exception:
                            entry = {}
                        entry["id"] = id_
                        entry["type"] = category
                        entry["title"] = title
                        entry["date_added"] = date_added
                        entries.append(entry)
            except Exception as e:
                print(f"Failed to load content for association: {e}")

        if not entries:
            QMessageBox.information(
                self,
                "No Content Available",
                "There are no content entries in Content Listings yet.",
            )
            return

        dlg = _AssociatedContentDialog(entries, self.assoc_content_ids, parent=self)
        if dlg.exec():
            self.assoc_content_ids = dlg.get_selected_ids()
            self._refresh_assoc_displays()

    def _select_associated_entities(self) -> None:
        entities = []
        if (
            self.vault_manager
            and hasattr(self.vault_manager, "raw_password")
            and self.vault_manager.raw_password
        ):
            db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
            password = self.vault_manager.raw_password
            salt = self.vault_manager.account_name
            try:
                rows = base.fetch_all_listings_secure(db_path, password, salt) # pyrefly: ignore [missing-attribute]
                for row in rows:
                    id_, category, title, metadata_json, date_added = row
                    if category == "Entity":
                        try:
                            entity = json.loads(metadata_json)
                        except Exception:
                            entity = {}
                        entity["id"] = id_
                        entity["name"] = title
                        entity["date_added"] = date_added
                        entities.append(entity)
            except Exception as e:
                print(f"Failed to load entities for association: {e}")

        if self._entity_id:
            entities = [e for e in entities if e.get("id") != self._entity_id]

        if not entities:
            QMessageBox.information(
                self,
                "No Entities Available",
                "There are no other entities available to associate.",
            )
            return

        dlg = _AssociatedEntitiesDialog(entities, self.assoc_entity_ids, parent=self)
        if dlg.exec():
            self.assoc_entity_ids = dlg.get_selected_ids()
            self._refresh_assoc_displays()

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
