import json
import uuid
import re
import os
import shutil

from pathlib import Path
from datetime import date
from typing import List, Dict, Any, Optional
from PySide6.QtCore import (
    Qt,
    Signal,
    Slot,
    QTimer,
    QThreadPool,
)
from PySide6.QtGui import QPixmap, QImage, QColor, QAction
from PySide6.QtWidgets import (
    QMenu,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QSpinBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QFrame,
    QGroupBox,
    QFormLayout,
    QSplitter,
    QDialog,
    QScrollArea,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QProgressDialog,
)

import base
import backend.src.constants as udef
from backend.src.constants import IMAGE_TOOLKIT_DIR
from backend.src.core.vault_manager import VaultManager  # noqa: F401
from ....styles.style import apply_shadow_effect, SHARED_BUTTON_STYLE
from ....components import DoubleClickableLabel
from ....constants.listings import (
    LISTINGS_FILE,  # noqa: F401
    ENTITIES_FILE,  # noqa: F401
    LISTING_IMAGES_DIR,
    ENTITY_TYPES,
    ENTITY_ROLES,
    ENTITY_TYPE_COLORS,
    ENTITY_ROLE_COLORS,
    CARD_SIZE,
    THUMB_SIZE,
    ENTITY_PLACEHOLDER,
)


# ---------------------------------------------------------------------------

from .listings_common import (
    _CARD_THUMB_CACHE,
    _ThumbWorker,
    open_file_location,
    _persist_splitter,
    _badge,
    _AssociatedEntitiesDialog,
    _AssociatedContentDialog,
    _SyncBackupWorker,
)


class _CreditDialog(QDialog):
    def __init__(self, credit_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Credit / Work Details")
        self.setMinimumWidth(400)
        self.setStyleSheet("background:#2c2f33; color:white;")

        self.data = credit_data or {}
        self.image_path = self.data.get("image_path", "")

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.f_title = QLineEdit()
        self.f_title.setPlaceholderText("Work / Show Title (e.g. Cowboy Bebop)")
        self.f_title.setText(self.data.get("title", ""))

        self.f_role = QLineEdit()
        self.f_role.setPlaceholderText(
            "Role / Character (e.g. Spike Spiegel / Director)"
        )
        self.f_role.setText(self.data.get("role", ""))

        self.f_year = QSpinBox()
        self.f_year.setRange(0, 2100)
        self.f_year.setValue(self.data.get("year", date.today().year))
        self.f_year.setSpecialValueText("Unknown")

        self.f_rating = QSpinBox()
        self.f_rating.setRange(0, 10)
        self.f_rating.setSpecialValueText("No rating")
        self.f_rating.setValue(self.data.get("rating", 0))

        self.f_notes = QTextEdit()
        self.f_notes.setPlaceholderText("Notes about this appearance / credit…")
        self.f_notes.setPlainText(self.data.get("notes", ""))
        self.f_notes.setFixedHeight(80)

        form.addRow("Work Title *", self.f_title)
        form.addRow("Role / Character", self.f_role)
        form.addRow("Year", self.f_year)
        form.addRow("Rating", self.f_rating)
        form.addRow("Notes", self.f_notes)
        layout.addLayout(form)

        # Image picker
        img_layout = QHBoxLayout()
        self.img_preview = DoubleClickableLabel()
        self.img_preview.setFixedSize(120, 120)
        self.img_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_preview.setStyleSheet("border:1px dashed #4f545c; border-radius:4px;")
        self._update_preview()
        img_layout.addWidget(self.img_preview)

        browse_btn = QPushButton("📁 Browse Image")
        browse_btn.clicked.connect(self._browse)
        img_layout.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(img_layout)

        # Buttons
        btns = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Work Image", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            self.image_path = path
            self._update_preview()

    def _update_preview(self):
        self.img_preview.set_image_path(self.image_path)
        if self.image_path and Path(self.image_path).exists():
            px = QPixmap(self.image_path).scaled(
                120,
                120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.img_preview.setPixmap(px)
        else:
            self.img_preview.setText("No Image")

    def get_data(self) -> Dict[str, Any]:
        return {
            "id": self.data.get("id") or str(uuid.uuid4()),
            "title": self.f_title.text().strip(),
            "role": self.f_role.text().strip(),
            "year": self.f_year.value(),
            "rating": self.f_rating.value(),
            "notes": self.f_notes.toPlainText().strip(),
            "image_path": self.image_path,
        }


# -------------------------------------------------------------------
# Associated Entities Dialog
# -------------------------------------------------------------------


class _EntityCard(QWidget):
    clicked = Signal(str)  # entity id
    delete_requested = Signal(str)  # entity id
    add_requested = Signal()

    def __init__(self, entity: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.entity = entity
        self._id = entity["id"]
        self.setFixedSize(CARD_SIZE + 10, CARD_SIZE + 50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("entity_card")
        self.setStyleSheet(
            "QWidget#entity_card{background:#2c2f33;border:2px solid #4f545c;"
            "border-radius:8px;}"
            "QWidget#entity_card:hover{border:2px solid #00bcd4;}"
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Thumbnail
        self.thumb_label = DoubleClickableLabel()
        self.thumb_label.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet("border:none;")
        self._apply_thumbnail(entity.get("image_path", ""))
        layout.addWidget(self.thumb_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Name
        name_lbl = QLabel(entity.get("name", "Unnamed"))
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setWordWrap(False)
        name_lbl.setStyleSheet(
            "color:#ffffff;font-weight:bold;font-size:11px;border:none;"
        )
        name_lbl.setFixedWidth(CARD_SIZE - 4)
        fm = name_lbl.fontMetrics()
        name_lbl.setText(
            fm.elidedText(
                entity.get("name", "Unnamed"),
                Qt.TextElideMode.ElideRight,
                CARD_SIZE - 10,
            )
        )
        name_lbl.setToolTip(entity.get("name", ""))
        layout.addWidget(name_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Badges row
        badge_row = QHBoxLayout()
        badge_row.setSpacing(4)
        t = entity.get("type", "Other")
        r = entity.get("role", "Other")
        badge_row.addWidget(_badge(t, ENTITY_TYPE_COLORS.get(t, "#607d8b")))
        badge_row.addWidget(_badge(r[:9], ENTITY_ROLE_COLORS.get(r, "#607d8b")))
        layout.addLayout(badge_row)

        # Associated content or credits count
        credits = entity.get("credit_list", [])
        assoc = entity.get("associated_content", [])
        assoc_count = len(assoc) if isinstance(assoc, list) else (1 if assoc else 0)
        if credits:
            info_text = f"Credits: {len(credits)}"
        elif assoc_count:
            info_text = f"Content: {assoc_count}"
        else:
            info_text = ""

        if info_text:
            info_lbl = QLabel(info_text)
            info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_lbl.setStyleSheet("color:#888; font-size:10px; border:none;")
            info_lbl.setFixedWidth(CARD_SIZE - 10)
            info_lbl.setText(
                fm.elidedText(info_text, Qt.TextElideMode.ElideRight, CARD_SIZE - 10)
            )
            layout.addWidget(info_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Rating stars
        rating = entity.get("rating", 0)
        if rating:
            stars = "★" * rating + "☆" * (10 - rating)
            r_lbl = QLabel(stars[:10])
            r_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            r_lbl.setStyleSheet("color:#f1c40f;font-size:9px;border:none;")
            layout.addWidget(r_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

    def _apply_thumbnail(self, path: str) -> None:
        self.thumb_label.set_image_path(path)
        if not path or not Path(path).exists():
            self.thumb_label.setText(ENTITY_PLACEHOLDER)
            self.thumb_label.setStyleSheet(
                "font-size:48px;color:#4f545c;background:#23272a;"
                "border-radius:6px;border:none;"
            )
            return

        cached = _CARD_THUMB_CACHE.get(path)
        if cached is not None:
            self.thumb_label.setPixmap(QPixmap.fromImage(cached))
            self.thumb_label.setStyleSheet("")
            return

        self.thumb_label.setText("")
        self.thumb_label.setStyleSheet(
            "background:#23272a;border-radius:6px;border:none;"
        )
        worker = _ThumbWorker(path, THUMB_SIZE)
        worker.signals.ready.connect(self._on_thumb_ready)
        QThreadPool.globalInstance().start(worker)

    @Slot(str, QImage)
    def _on_thumb_ready(self, path: str, img: QImage) -> None:
        if path == self.thumb_label.image_path:
            self.thumb_label.setPixmap(QPixmap.fromImage(img))
            self.thumb_label.setStyleSheet("")

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._id)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#2c2f33; color:white; border:1px solid #4f545c; }"
            "QMenu::item:selected { background:#00bcd4; color:black; }"
        )

        edit_act = QAction("✎ Edit Details", self)
        edit_act.triggered.connect(lambda: self.clicked.emit(self._id))
        menu.addAction(edit_act)

        add_act = QAction("＋ Add New Entity", self)
        add_act.triggered.connect(lambda: self.add_requested.emit())
        menu.addAction(add_act)

        img_path = self.entity.get("image_path", "")
        if img_path:
            menu.addSeparator()
            open_img_loc_act = QAction("📂 Open Image Location", self)
            open_img_loc_act.triggered.connect(
                lambda _, path=img_path: open_file_location(path)
            )
            menu.addAction(open_img_loc_act)

        menu.addSeparator()

        del_act = QAction("🗑 Remove Entity", self)
        del_act.triggered.connect(lambda: self.delete_requested.emit(self._id))
        menu.addAction(del_act)

        menu.exec(self.mapToGlobal(pos))


# -------------------------------------------------------------------
# Detail / edit panel (Content Listings)
# -------------------------------------------------------------------


class _EntityDetailPanel(QWidget):
    saved = Signal(dict)
    deleted = Signal(str)

    def __init__(self, parent=None, vault_manager=None):
        super().__init__(parent)
        self.vault_manager = vault_manager
        self._entity_id: Optional[str] = None
        self._image_path = ""
        self._credit_data = []
        self.assoc_content_ids: List[str] = []
        self.assoc_entity_ids: List[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Image picker
        img_row = QHBoxLayout()
        self.img_preview = DoubleClickableLabel()
        self.img_preview.setFixedSize(160, 160)
        self.img_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(
            "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
        )
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

        # Show visibility immediately; defer heavy loads off the click path.
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
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
        )
        if path:
            LISTING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            self._entity_id = self._entity_id or str(uuid.uuid4())
            orig_p = Path(path)
            dest_p = LISTING_IMAGES_DIR / f"{self._entity_id}{orig_p.suffix}"
            try:
                shutil.copy2(path, dest_p)
                self._image_path = str(dest_p.absolute())
            except Exception as e:
                print(f"Failed to copy image: {e}")
                self._image_path = path
            self._refresh_image()

    def _refresh_image(self):
        path = self._image_path
        self.img_preview.set_image_path(path)
        if not path or not Path(path).exists():
            self.img_preview.clear()
            self.img_preview.setText("No Image")
            self.img_preview.setStyleSheet(
                "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
            )
            return
        cache_key = f"preview160:{path}"
        cached = _CARD_THUMB_CACHE.get(cache_key)
        if cached is not None:
            self.img_preview.setPixmap(QPixmap.fromImage(cached))
            self.img_preview.setStyleSheet(
                "border:2px solid #4f545c;border-radius:8px;"
            )
            return
        worker = _ThumbWorker(path, 160)
        worker.signals.ready.connect(self._on_preview_ready)
        QThreadPool.globalInstance().start(worker)

    @Slot(str, QImage)
    def _on_preview_ready(self, path: str, img: QImage) -> None:
        if path == self.img_preview.image_path:
            _CARD_THUMB_CACHE[f"preview160:{path}"] = img
            self.img_preview.setPixmap(QPixmap.fromImage(img))
            self.img_preview.setStyleSheet(
                "border:2px solid #4f545c;border-radius:8px;"
            )

    def _refresh_credit_list(self):
        while self.credit_list_layout.count():
            item = self.credit_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

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

            # Thumbnail — async to keep _refresh_credit_list snappy
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

    # ------------------------------------------------------------------
    # Association helpers
    # ------------------------------------------------------------------

    def _refresh_assoc_displays(self) -> None:
        """Refresh both association display fields from current ID lists."""
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
            rows = base.fetch_all_listings_secure(db_path, password, salt)

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
                rows = base.fetch_all_listings_secure(db_path, password, salt)
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
                rows = base.fetch_all_listings_secure(db_path, password, salt)
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

        # Exclude self from the list
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


class _EntityDirectoryImportDialog(QDialog):
    """One-shot wizard: pick a directory of entity images → review detected
    entities → configure shared metadata → confirm or cancel import."""

    def __init__(self, existing_names: "set[str]", parent=None):
        super().__init__(parent)
        self.setWindowTitle("📂 Import Entities from Image Directory")
        self.setMinimumSize(840, 620)
        self.setStyleSheet(
            "QDialog { background:#2c2f33; color:white; }"
            "QLabel  { color:white; }"
            "QLineEdit, QSpinBox, QComboBox { background:#23272a; color:white;"
            "  border:1px solid #4f545c; border-radius:4px; padding:4px; }"
            "QGroupBox { border:1px solid #4f545c; border-radius:6px;"
            "  margin-top:8px; color:#00bcd4; font-weight:bold; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }"
        )

        self._existing_names = existing_names  # lowercase normalised set
        self._scan_result: list = []  # list of tuples: (first_name, last_name, file_path)
        self._directory = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # ── Directory picker row ──────────────────────────────────────
        dir_group = QGroupBox("Image Directory")
        dir_row = QHBoxLayout(dir_group)
        dir_row.setSpacing(6)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText(
            "Select the folder that contains your entity image files…"
        )
        self._dir_edit.setReadOnly(True)
        browse_btn = QPushButton("📁 Browse…")
        browse_btn.setFixedWidth(100)
        browse_btn.clicked.connect(self._browse)
        scan_btn = QPushButton("🔍 Scan")
        scan_btn.setFixedWidth(80)
        scan_btn.clicked.connect(self._do_scan)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(browse_btn)
        dir_row.addWidget(scan_btn)
        root.addWidget(dir_group)

        # ── Middle: table left | options right ────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left — detected-entities table
        left = QWidget()
        left_vbox = QVBoxLayout(left)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(6)

        self._status_lbl = QLabel("Scan a directory to detect entity images.")
        self._status_lbl.setStyleSheet("color:#888; font-size:11px;")
        left_vbox.addWidget(self._status_lbl)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["", "Detected Name", "Filename", "Status"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._table.setColumnWidth(0, 32)
        self._table.setColumnWidth(3, 120)
        self._table.verticalHeader().hide()
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget { background:#23272a; alternate-background-color:#252830;"
            "  border:1px solid #4f545c; border-radius:6px; gridline-color:#3a3d42; }"
            "QTableWidget::item { color:white; padding:3px; }"
            "QTableWidget::item:selected { background:#00bcd4; color:black; }"
            "QHeaderView::section { background:#2c2f33; color:#888; border:none; padding:4px; }"
        )
        left_vbox.addWidget(self._table, 1)

        sel_row = QHBoxLayout()
        sel_all_btn = QPushButton("☑ Select All New")
        sel_all_btn.setFixedHeight(36)
        sel_all_btn.setStyleSheet("padding: 6px 12px;")
        sel_all_btn.clicked.connect(self._select_all_new)
        sel_none_btn = QPushButton("☐ Deselect All")
        sel_none_btn.setFixedHeight(36)
        sel_none_btn.setStyleSheet("padding: 6px 12px;")
        sel_none_btn.clicked.connect(self._deselect_all)
        sel_row.addWidget(sel_all_btn)
        sel_row.addWidget(sel_none_btn)
        sel_row.addStretch()
        left_vbox.addLayout(sel_row)
        splitter.addWidget(left)

        # Right — metadata options
        right = QWidget()
        right_vbox = QVBoxLayout(right)
        right_vbox.setContentsMargins(6, 0, 0, 0)
        right_vbox.setSpacing(8)

        meta_group = QGroupBox("Metadata Applied to All New Entities")
        meta_form = QFormLayout(meta_group)
        meta_form.setSpacing(8)

        self._f_type = QComboBox()
        self._f_type.addItems(ENTITY_TYPES)
        self._f_type.setCurrentText("Person")

        self._f_role = QComboBox()
        self._f_role.addItems(ENTITY_ROLES)
        self._f_role.setCurrentText("Director")

        self._f_rating = QSpinBox()
        self._f_rating.setRange(0, 10)
        self._f_rating.setValue(0)

        self._f_year = QSpinBox()
        self._f_year.setRange(0, 2100)
        self._f_year.setValue(0)
        self._f_year.setSpecialValueText("Unknown")

        meta_form.addRow("Type:", self._f_type)
        meta_form.addRow("Role:", self._f_role)
        meta_form.addRow("Rating:", self._f_rating)
        meta_form.addRow("Active Year:", self._f_year)
        right_vbox.addWidget(meta_group)
        right_vbox.addStretch()

        info_lbl = QLabel(
            "<small>"
            "<b>Filename format expected:</b><br>"
            "<code>&lt;First Name&gt; &lt;Last Name&gt;&lt;Optional Number&gt;.ext</code><br><br>"
            "<b>What gets created:</b><br>"
            "• First name and last name parsed from the image filename<br>"
            "• Optional trailing digits are stripped from the entity name<br>"
            "• Image copied and associated automatically as entity profile picture"
            "</small>"
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("color:#888; font-size:10px; border:none;")
        right_vbox.addWidget(info_lbl)
        splitter.addWidget(right)

        splitter.setSizes([520, 300])
        _persist_splitter(splitter, "entity_directory_import_dialog")
        root.addWidget(splitter, 1)

        # ── Confirm / cancel ──────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(90)
        cancel_btn.clicked.connect(self.reject)
        self._import_btn = QPushButton("📥 Import Selected")
        self._import_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        self._import_btn.setFixedWidth(150)
        self._import_btn.setEnabled(False)
        self._import_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._import_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    def _browse(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Entity Image Directory",
            self._directory or str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
            | QFileDialog.Option.DontResolveSymlinks
            | QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            self._directory = directory
            self._dir_edit.setText(directory)
            self._do_scan()

    def _do_scan(self):
        directory = self._dir_edit.text().strip() or self._directory
        if not directory or not Path(directory).is_dir():
            QMessageBox.warning(
                self, "Invalid Directory", "Please select a valid directory first."
            )
            return
        self._directory = directory

        # Scan for images
        self._scan_result = []
        p = Path(directory)
        valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

        try:
            for item in p.iterdir():
                if item.is_file() and item.suffix.lower() in valid_exts:
                    stem = item.stem
                    # remove optional trailing number and spaces
                    clean_stem = re.sub(r"\s*\d+$", "", stem).strip()
                    parts = clean_stem.split()
                    if not parts:
                        continue
                    first_name = parts[0]
                    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                    self._scan_result.append(
                        (first_name, last_name, str(item.absolute()))
                    )
        except Exception as e:
            QMessageBox.critical(self, "Scan Error", f"Failed to scan directory: {e}")
            return

        self._populate_table()

    def _populate_table(self):
        self._table.setRowCount(0)
        new_count = exists_count = 0

        for first_name, last_name, file_path in sorted(
            self._scan_result, key=lambda x: f"{x[0]} {x[1]}".lower()
        ):
            full_name = f"{first_name} {last_name}".strip()
            already = full_name.lower() in self._existing_names
            if already:
                exists_count += 1
            else:
                new_count += 1

            row = self._table.rowCount()
            self._table.insertRow(row)

            # Col 0 – checkbox (wrapped in a centred container)
            chk = QCheckBox()
            chk.setChecked(not already)
            chk.setStyleSheet("QCheckBox { margin-left:6px; }")
            container = QWidget()
            c_lay = QHBoxLayout(container)
            c_lay.addWidget(chk)
            c_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_lay.setContentsMargins(0, 0, 0, 0)
            self._table.setCellWidget(row, 0, container)

            # Col 1 – Detected Name
            name_item = QTableWidgetItem(full_name)
            self._table.setItem(row, 1, name_item)

            # Col 2 – Filename
            file_item = QTableWidgetItem(Path(file_path).name)
            file_item.setToolTip(file_path)
            self._table.setItem(row, 2, file_item)

            # Col 3 – new / already-exists badge
            if already:
                st_item = QTableWidgetItem("⚠ Already exists")
                st_item.setForeground(QColor("#f39c12"))
            else:
                st_item = QTableWidgetItem("✓ New")
                st_item.setForeground(QColor("#2ecc71"))
            self._table.setItem(row, 3, st_item)

        total = len(self._scan_result)
        self._status_lbl.setText(
            f"Found {total} images — {new_count} new, {exists_count} already in entities."
        )
        self._import_btn.setEnabled(total > 0)

    # ------------------------------------------------------------------
    def _select_all_new(self):
        for row in range(self._table.rowCount()):
            st = self._table.item(row, 3)
            if st and "New" in st.text():
                self._set_row_check(row, True)

    def _deselect_all(self):
        for row in range(self._table.rowCount()):
            self._set_row_check(row, False)

    def _set_row_check(self, row: int, state: bool):
        cw = self._table.cellWidget(row, 0)
        if cw:
            chk = cw.findChild(QCheckBox)
            if chk:
                chk.setChecked(state)

    # ------------------------------------------------------------------
    def get_selected_entities(self) -> "list[tuple[str, str, str]]":
        """Return the list of (first_name, last_name, file_path) whose checkboxes are ticked."""
        selected = []
        for row in range(self._table.rowCount()):
            cw = self._table.cellWidget(row, 0)
            if cw:
                chk = cw.findChild(QCheckBox)
                if chk and chk.isChecked():
                    # Match by index in the sorted list
                    first_name, last_name, file_path = sorted(
                        self._scan_result, key=lambda x: f"{x[0]} {x[1]}".lower()
                    )[row]
                    selected.append((first_name, last_name, file_path))
        return selected

    def get_metadata(self) -> dict:
        return {
            "type": self._f_type.currentText(),
            "role": self._f_role.currentText(),
            "rating": self._f_rating.value(),
            "year": self._f_year.value(),
        }


# -------------------------------------------------------------------
# Vector Search Init Thread
# -------------------------------------------------------------------


# -------------------------------------------------------------------
# Recommendation Dialog
# -------------------------------------------------------------------


class EntityListingsSubTab(QWidget):
    listings_changed = Signal()  # emitted when listings.json is updated by cross-sync

    def __init__(self, parent=None, vault_manager=None):
        super().__init__(parent)
        self.vault_manager = vault_manager
        self._entities: List[Dict[str, Any]] = []
        self._selected_id: Optional[str] = None
        self._filter_type = "All"
        self._filter_role = "All"
        self._search_query = ""

        # ---- Root layout ----
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        # ---- Toolbar ----
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        title_lbl = QLabel("👥 Entity Listings")
        title_lbl.setStyleSheet("font-size:18px;font-weight:bold;color:#00bcd4;")
        toolbar.addWidget(title_lbl)
        toolbar.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search entities…")
        self.search_box.setFixedWidth(200)
        self.search_box.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_box)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["All Types"] + ENTITY_TYPES)
        self.type_combo.currentTextChanged.connect(self._on_type_filter)
        toolbar.addWidget(self.type_combo)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["All Roles"] + ENTITY_ROLES)
        self.role_combo.currentTextChanged.connect(self._on_role_filter)
        toolbar.addWidget(self.role_combo)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            [
                "Sort by: Name",
                "Sort by: Rating",
                "Sort by: Type",
                "Sort by: Role",
                "Sort by: Date Added",
                "Sort by: Credits Count",
            ]
        )
        self.sort_combo.setFixedWidth(150)
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_combo)

        self.sort_order_combo = QComboBox()
        self.sort_order_combo.addItems(["Ascending", "Descending"])
        self.sort_order_combo.setFixedWidth(100)
        self.sort_order_combo.currentTextChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_order_combo)

        # ── Pair 1: Add Entity (top) / Import Dir (bottom) ──────────────
        entity_pair = QWidget()
        entity_pair_vbox = QVBoxLayout(entity_pair)
        entity_pair_vbox.setContentsMargins(0, 0, 0, 0)
        entity_pair_vbox.setSpacing(3)

        add_btn = QPushButton("＋ Add Entity")
        add_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        add_btn.setFixedWidth(120)
        add_btn.clicked.connect(self._on_add_new)
        apply_shadow_effect(add_btn)

        import_dir_btn = QPushButton("📂 Import Dir")
        import_dir_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        import_dir_btn.setFixedWidth(120)
        import_dir_btn.setToolTip(
            "Scan an entity image directory and auto-create listings."
        )
        import_dir_btn.clicked.connect(self._on_import_from_directory)
        apply_shadow_effect(import_dir_btn)

        entity_pair_vbox.addWidget(add_btn)
        entity_pair_vbox.addWidget(import_dir_btn)
        toolbar.addWidget(entity_pair)

        # ── Pair 2: Sync Backup (top) / Update Backup (bottom) ─────────
        backup_pair = QWidget()
        backup_pair_vbox = QVBoxLayout(backup_pair)
        backup_pair_vbox.setContentsMargins(0, 0, 0, 0)
        backup_pair_vbox.setSpacing(3)

        sync_btn = QPushButton("🔄 Sync Backup")
        sync_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        sync_btn.setFixedWidth(130)
        sync_btn.clicked.connect(self._synchronize_listings)
        apply_shadow_effect(sync_btn)

        update_btn = QPushButton("⚡ Update Backup")
        update_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        update_btn.setFixedWidth(130)
        update_btn.clicked.connect(self._update_encrypted_backup)
        apply_shadow_effect(update_btn)

        backup_pair_vbox.addWidget(sync_btn)
        backup_pair_vbox.addWidget(update_btn)
        toolbar.addWidget(backup_pair)

        root.addLayout(toolbar)

        # ---- Stats bar ----
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color:#888;font-size:11px;")
        root.addWidget(self.stats_label)

        # ---- Splitter: gallery | detail ----
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Gallery
        gallery_container = QWidget()
        gallery_vbox = QVBoxLayout(gallery_container)
        gallery_vbox.setContentsMargins(0, 0, 0, 0)
        gallery_vbox.setSpacing(0)

        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setStyleSheet(
            "QScrollArea{border:1px solid #4f545c;border-radius:8px;background:#23272a;}"
        )
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background:#23272a;")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(10, 10, 10, 10)
        self.gallery_scroll.setWidget(self._grid_widget)
        gallery_vbox.addWidget(self.gallery_scroll)
        splitter.addWidget(gallery_container)

        # Detail panel (wrapped in a scroll area)
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setStyleSheet(
            "QScrollArea{border:1px solid #4f545c;border-radius:8px;background:#2c2f33;}"
        )
        self._detail = _EntityDetailPanel(vault_manager=self.vault_manager)
        self._detail.saved.connect(self._on_entity_saved)
        self._detail.deleted.connect(self._on_entity_deleted)
        detail_scroll.setWidget(self._detail)
        splitter.addWidget(detail_scroll)
        _persist_splitter(splitter, "EntityListingsSubTab_main")

        splitter.setSizes([680, 340])
        splitter.setHandleWidth(6)
        root.addWidget(splitter, 1)

        # Context Menu for Gallery background
        self.gallery_scroll.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.gallery_scroll.customContextMenuRequested.connect(
            self._show_gallery_context_menu
        )

        # ---- Load data ----
        self._load_data()
        self._rebuild_gallery()
        self._detail.clear_for_new()

        # Debounced resize for EntityListingsSubTab.
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(120)
        self._resize_timer.timeout.connect(self._rebuild_gallery)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_data(self):
        self._entities = []

        if (
            self.vault_manager
            and hasattr(self.vault_manager, "raw_password")
            and self.vault_manager.raw_password
        ):
            db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
            password = self.vault_manager.raw_password
            salt = self.vault_manager.account_name
            try:
                rows = base.fetch_all_listings_secure(db_path, password, salt)
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
                        self._entities.append(entity)
            except Exception as e:
                print(f"[EntityListingsSubTab] Failed to load from secure DB: {e}")

    def _save_data(self):
        if (
            self.vault_manager
            and hasattr(self.vault_manager, "raw_password")
            and self.vault_manager.raw_password
        ):
            db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
            password = self.vault_manager.raw_password
            salt = self.vault_manager.account_name
            try:
                rows = base.fetch_all_listings_secure(db_path, password, salt)
                for row in rows:
                    id_, category, _, _, _ = row
                    if category == "Entity":
                        base.delete_listing_secure(db_path, password, salt, id_)
                for entity in self._entities:
                    eid = entity.get("id")
                    ename = entity.get("name", "")
                    edate = entity.get("date_added", "")
                    meta = dict(entity)
                    base.insert_listing_secure(
                        db_path,
                        password,
                        salt,
                        eid,
                        "Entity",
                        ename,
                        json.dumps(meta, ensure_ascii=False),
                        edate,
                        [],
                    )
            except Exception as e:
                print(
                    f"[EntityListingsSubTab] Failed to save entities to secure DB: {e}"
                )

    # ------------------------------------------------------------------
    # Gallery
    # ------------------------------------------------------------------
    def _filtered_entities(self) -> List[Dict[str, Any]]:
        result = self._entities
        if self._filter_type and self._filter_type not in (
            "All",
            "All Types",
            "None",
            "",
        ):
            result = [e for e in result if e.get("type") == self._filter_type]
        if self._filter_role not in ("All", "All Roles"):
            result = [e for e in result if e.get("role") == self._filter_role]
        if self._search_query:
            q = self._search_query.lower()
            content_titles_map: Dict[str, str] = {}
            if (
                self.vault_manager
                and hasattr(self.vault_manager, "raw_password")
                and self.vault_manager.raw_password
            ):
                db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
                password = self.vault_manager.raw_password
                salt = self.vault_manager.account_name
                try:
                    rows = base.fetch_all_listings_secure(db_path, password, salt)
                    for row in rows:
                        id_, category, title, metadata_json, date_added = row
                        if category != "Entity":
                            content_titles_map[id_] = title.lower()
                except Exception:
                    pass

            filtered_ents = []
            for e in result:
                if q in e.get("name", "").lower() or q in e.get("notes", "").lower():
                    filtered_ents.append(e)
                    continue
                # Search associated_content (list of IDs → resolve titles)
                assoc_c = e.get("associated_content", [])
                if isinstance(assoc_c, list):
                    if any(q in content_titles_map.get(cid, "") for cid in assoc_c):
                        filtered_ents.append(e)
                        continue
                else:
                    if q in str(assoc_c).lower():
                        filtered_ents.append(e)
                        continue
                # Search associated_entities (IDs → entity names)
                # assoc_e = e.get("associated_entities", [])
                # Entity names aren't cached here — skip for now
            result = filtered_ents

        # Sorting logic
        sort_text = self.sort_combo.currentText()
        is_descending = self.sort_order_combo.currentText() == "Descending"

        def get_sort_key(entity):
            if "Name" in sort_text:
                return (entity.get("name") or "").lower()
            elif "Rating" in sort_text:
                return entity.get("rating") or 0
            elif "Type" in sort_text:
                return (entity.get("type") or "").lower()
            elif "Role" in sort_text:
                return (entity.get("role") or "").lower()
            elif "Date Added" in sort_text:
                return entity.get("date_added") or ""
            elif "Credits Count" in sort_text:
                return len(entity.get("credit_list") or [])
            return (entity.get("name") or "").lower()

        result = sorted(result, key=get_sort_key, reverse=is_descending)
        return result

    def _rebuild_gallery(self):
        # Clear old widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        visible = self._filtered_entities()

        if not visible:
            placeholder = QLabel(
                "No entities found.\nClick '＋ Add Entity' to get started."
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color:#555;font-size:14px;")
            self._grid.addWidget(placeholder, 0, 0)
        else:
            cols = max(1, self.gallery_scroll.width() // (CARD_SIZE + 20))
            for i, entity in enumerate(visible):
                card = _EntityCard(entity)
                card.clicked.connect(self._on_card_clicked)
                card.add_requested.connect(self._on_add_new)
                card.delete_requested.connect(self._on_card_delete_requested)
                self._grid.addWidget(card, i // cols, i % cols)

        # Stats
        total = len(self._entities)
        completed = sum(1 for e in self._entities if e.get("rating", 0) >= 8)
        self.stats_label.setText(
            f"{total} entities total · {completed} highly rated (>=8) · showing {len(visible)}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        # Gallery is always up-to-date from explicit _rebuild_gallery() calls;
        # rebuilding on every tab switch caused the freeze (see ContentListingsSubTab).

    def _on_sort_changed(self, text):
        self._rebuild_gallery()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    @Slot(str)
    def _on_card_clicked(self, entity_id: str):
        self._selected_id = entity_id
        entity = next((e for e in self._entities if e["id"] == entity_id), None)
        if entity:
            self._detail.load_entity(entity)

    def _on_card_delete_requested(self, entity_id: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Permanently remove this entity from your listings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._on_entity_deleted(entity_id)

    def _show_gallery_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#2c2f33; color:white; border:1px solid #4f545c; }"
            "QMenu::item:selected { background:#00bcd4; color:black; }"
        )
        add_act = QAction("＋ Add New Entity", self)
        add_act.triggered.connect(self._on_add_new)
        menu.addAction(add_act)
        menu.exec(self.gallery_scroll.mapToGlobal(pos))

    @Slot()
    def _on_import_from_directory(self):
        """Open the entity directory-import wizard and create listings for new entities."""
        existing_names = {e.get("name", "").lower() for e in self._entities}
        dlg = _EntityDirectoryImportDialog(existing_names, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected_entities = dlg.get_selected_entities()
        if not selected_entities:
            QMessageBox.information(
                self,
                "Nothing to Import",
                "No entities were selected. Nothing was imported.",
            )
            return

        meta = dlg.get_metadata()
        today = str(date.today())
        created = 0

        # Ensure listing-images directory exists
        LISTING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        for first_name, last_name, src_file_path in selected_entities:
            # Generate unique entity ID
            entity_id = "ent-" + uuid.uuid4().hex[:8]

            # Copy profile image to listing-images directory
            src_path = Path(src_file_path)
            dest_img_name = f"{entity_id}{src_path.suffix}"
            dest_img_path = LISTING_IMAGES_DIR / dest_img_name

            try:
                shutil.copy2(src_path, dest_img_path)
                image_path = str(dest_img_path)
            except Exception as e:
                print(f"Failed to copy entity image: {e}")
                image_path = ""

            entity = {
                "id": entity_id,
                "name": f"{first_name} {last_name}".strip(),
                "first_name": first_name,
                "last_name": last_name,
                "type": meta["type"],
                "role": meta["role"],
                "rating": meta["rating"],
                "year": meta["year"],
                "image_path": image_path,
                "notes": "",
                "credit_list": [],
                "associated_content": [],
                "associated_entities": [],
                "date_added": today,
            }

            self._entities.insert(0, entity)
            created += 1

        if created:
            self._save_data()
            self._rebuild_gallery()
            QMessageBox.information(
                self,
                "Import Complete",
                f"Successfully imported {created} new entity"
                f"{'s' if created != 1 else ''}.",
            )
        else:
            QMessageBox.information(
                self,
                "No New Entries",
                "All selected entities already had listings — nothing was added.",
            )

    @Slot()
    def _on_add_new(self):
        self._selected_id = None
        self._detail.clear_for_new()

    @Slot(dict)
    def _on_entity_saved(self, entity: Dict[str, Any]):
        idx = next(
            (i for i, e in enumerate(self._entities) if e["id"] == entity["id"]), None
        )
        if idx is not None:
            self._entities[idx] = entity
        else:
            self._entities.insert(0, entity)
        self._save_data()
        if self._sync_listings_for_entity(entity):
            self.listings_changed.emit()
        self._rebuild_gallery()
        self._detail.load_entity(entity)

    @Slot(str)
    def _on_entity_deleted(self, entity_id: str):
        self._entities = [e for e in self._entities if e["id"] != entity_id]
        self._save_data()
        if self._remove_entity_from_listings(entity_id):
            self.listings_changed.emit()
        self._rebuild_gallery()
        self._detail.clear_for_new()

    def _sync_listings_for_entity(self, entity: Dict[str, Any]) -> bool:
        """Keep listings in sync in secure DB: each associated content entry gains this entity's
        ID in its associated_entities list; removed entries lose it."""
        entity_id = entity.get("id")
        if not entity_id:
            return False
        new_assoc = set(entity.get("associated_content", []))
        if (
            self.vault_manager
            and hasattr(self.vault_manager, "raw_password")
            and self.vault_manager.raw_password
        ):
            db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
            password = self.vault_manager.raw_password
            salt = self.vault_manager.account_name
            try:
                rows = base.fetch_all_listings_secure(db_path, password, salt)
                listings = []
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
                        listings.append(entry)

                changed = False
                for listing in listings:
                    lid = listing.get("id")
                    if not lid:
                        continue
                    current = set(listing.get("associated_entities", []))
                    if lid in new_assoc and entity_id not in current:
                        current.add(entity_id)
                        listing["associated_entities"] = list(current)
                        changed = True
                    elif lid not in new_assoc and entity_id in current:
                        current.discard(entity_id)
                        listing["associated_entities"] = list(current)
                        changed = True

                if changed:
                    for entry in listings:
                        base.delete_listing_secure(db_path, password, salt, entry["id"])
                        meta = dict(entry)
                        base.insert_listing_secure(
                            db_path,
                            password,
                            salt,
                            entry["id"],
                            entry.get("type", "Anime"),
                            entry.get("title", ""),
                            json.dumps(meta, ensure_ascii=False),
                            entry.get("date_added", ""),
                            [],
                        )
                return changed
            except Exception as e:
                print(
                    f"[EntityListingsSubTab] Failed to sync listings in secure DB: {e}"
                )
        return False

    def _remove_entity_from_listings(self, entity_id: str) -> bool:
        """Remove a deleted entity's ID from all content entries' associated_entities in secure DB."""
        if (
            self.vault_manager
            and hasattr(self.vault_manager, "raw_password")
            and self.vault_manager.raw_password
        ):
            db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
            password = self.vault_manager.raw_password
            salt = self.vault_manager.account_name
            try:
                rows = base.fetch_all_listings_secure(db_path, password, salt)
                listings = []
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
                        listings.append(entry)

                changed = False
                for listing in listings:
                    current = set(listing.get("associated_entities", []))
                    if entity_id in current:
                        current.discard(entity_id)
                        listing["associated_entities"] = list(current)
                        changed = True

                if changed:
                    for entry in listings:
                        base.delete_listing_secure(db_path, password, salt, entry["id"])
                        meta = dict(entry)
                        base.insert_listing_secure(
                            db_path,
                            password,
                            salt,
                            entry["id"],
                            entry.get("type", "Anime"),
                            entry.get("title", ""),
                            json.dumps(meta, ensure_ascii=False),
                            entry.get("date_added", ""),
                            [],
                        )
                return changed
            except Exception as e:
                print(
                    f"[EntityListingsSubTab] Failed to clean up listings in secure DB: {e}"
                )
        return False

    def _on_external_reload(self) -> None:
        """Called when another subtab modifies entities.json; refreshes in-memory data."""
        self._load_data()
        self._rebuild_gallery()

    @Slot(str)
    def _on_search(self, text: str):
        self._search_query = text
        self._rebuild_gallery()

    @Slot(str)
    def _on_type_filter(self, text: str):
        self._filter_type = text
        self._rebuild_gallery()

    @Slot(str)
    def _on_role_filter(self, text: str):
        self._filter_role = text
        self._rebuild_gallery()

    @Slot()
    def _synchronize_listings(self):
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Vault manager is not initialized or active. Please log in to sync.",
            )
            return

        secrets_dir = Path(udef.ROOT_DIR) / "assets" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        enc_file_path = str(secrets_dir / "entities.json.enc")

        if not os.path.exists(enc_file_path):
            QMessageBox.warning(
                self,
                "Backup Not Found",
                "No encrypted entities backup file found to synchronize from. Use 'Update Backup' first to generate it.",
            )
            return

        db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")

        # Create progress dialog
        self.progress_dialog = QProgressDialog(
            "Starting synchronization...", None, 0, 100, self
        )
        self.progress_dialog.setWindowTitle("Synchronizing Backup")
        self.progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.setWindowFlags(
            self.progress_dialog.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint
        )
        self.progress_dialog.show()

        # Start background thread
        self._sync_worker = _SyncBackupWorker(
            "sync",
            "Entity",
            {
                "vault_manager": self.vault_manager,
                "enc_file_path": enc_file_path,
                "local_entries": self._entities,
                "db_path": db_path,
            },
        )
        self._sync_worker.progress.connect(self._on_sync_progress)
        self._sync_worker.finished.connect(self._on_sync_finished)
        self._sync_worker.start()

    def _on_sync_progress(self, percent, text):
        dlg = getattr(self, "progress_dialog", None)
        if dlg is not None:
            dlg.setLabelText(text)
            dlg.setValue(percent)

    def _on_sync_finished(self, success, message, result_data):
        if getattr(self, "progress_dialog", None):
            self.progress_dialog.close()
            self.progress_dialog = None

        if success:
            merged_entries, synced_imgs = result_data
            self._entities = merged_entries
            self._rebuild_gallery()

            img_info = (
                f"\nAlso restored {synced_imgs} missing image(s) from backup."
                if synced_imgs
                else ""
            )
            QMessageBox.information(
                self,
                "Synchronization Complete",
                f"Successfully synchronized entities!\nMerged local and backup entries to a total of {len(merged_entries)} entries.{img_info}",
            )
        else:
            QMessageBox.critical(
                self,
                "Sync Error",
                f"An error occurred during synchronization:\n{message}",
            )

    @Slot()
    def _update_encrypted_backup(self):
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Vault manager is not initialized or active. Please log in to update backup.",
            )
            return

        secrets_dir = Path(udef.ROOT_DIR) / "assets" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        enc_file_path = str(secrets_dir / "entities.json.enc")

        # Create progress dialog
        self.progress_dialog = QProgressDialog("Starting backup...", None, 0, 100, self)
        self.progress_dialog.setWindowTitle("Updating Backup")
        self.progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.setWindowFlags(
            self.progress_dialog.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint
        )
        self.progress_dialog.show()

        # Start background thread
        self._backup_worker = _SyncBackupWorker(
            "backup",
            "Entity",
            {
                "vault_manager": self.vault_manager,
                "enc_file_path": enc_file_path,
                "entries": self._entities,
            },
        )
        self._backup_worker.progress.connect(self._on_backup_progress)
        self._backup_worker.finished.connect(self._on_backup_finished)
        self._backup_worker.start()

    def _on_backup_progress(self, percent, text):
        dlg = getattr(self, "progress_dialog", None)
        if dlg is not None:
            dlg.setLabelText(text)
            dlg.setValue(percent)

    def _on_backup_finished(self, success, message, result_data):
        if getattr(self, "progress_dialog", None):
            self.progress_dialog.close()
            self.progress_dialog = None

        if success:
            backup_count = result_data
            img_info = (
                f"\nAlso backed up {backup_count} image(s) to multi-part archive."
                if backup_count
                else ""
            )
            QMessageBox.information(
                self,
                "Backup Updated",
                f"Successfully generated encrypted backup entities file with {len(self._entities)} entries.{img_info}",
            )
        else:
            QMessageBox.critical(
                self,
                "Backup Error",
                f"An error occurred while generating backup:\n{message}",
            )


# -------------------------------------------------------------------
# Main tab: Listings Tab containing the split sub-tabs
# -------------------------------------------------------------------
