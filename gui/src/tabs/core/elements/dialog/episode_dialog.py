import uuid
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QDialog,
    QDateEdit,
)

from gui.src.constants.listings import LISTING_IMAGES_DIR
from gui.src.styles import SHARED_BUTTON_STYLE
from gui.src.components.frame_selection_dialog import FrameSelectionDialog
from gui.src.tabs.core.elements.dialog.common.base_sub_item_dialog import BaseSubItemDialog


class _EpisodeDialog(BaseSubItemDialog):
    def __init__(self, episode_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__("Episode / Chapter Details", parent)
        self.data = episode_data or {}
        self.image_path = self.data.get("image_path", "")

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.f_number = QSpinBox()
        self.f_number.setRange(1, 999999)
        self.f_number.setValue(self.data.get("number", 1))

        self.f_title = QLineEdit()
        self.f_title.setPlaceholderText("Episode Title (optional)")
        self.f_title.setText(self.data.get("title", ""))

        self.f_date = QDateEdit()
        self.f_date.setCalendarPopup(True)
        d_str = self.data.get("date_watched")
        if d_str:
            self.f_date.setDate(date.fromisoformat(d_str))  # pyrefly: ignore [bad-argument-type]
        else:
            self.f_date.setDate(date.today()) # pyrefly: ignore [bad-argument-type]

        self.f_rating = QSpinBox()
        self.f_rating.setRange(0, 10)
        self.f_rating.setSpecialValueText("No rating")
        self.f_rating.setValue(self.data.get("rating", 0))

        self.f_review = QTextEdit()
        self.f_review.setPlaceholderText("Episode notes / review…")
        self.f_review.setPlainText(self.data.get("review", ""))
        self.f_review.setFixedHeight(80)

        self.f_local_file = QLineEdit()
        self.f_local_file.setPlaceholderText("Local File path (optional)")
        self.f_local_file.setText(self.data.get("local_file", ""))

        local_file_btn = QPushButton("📁 Browse")
        local_file_btn.setStyleSheet(
            "background-color:#4f545c; padding: 4px 8px; color: white;"
        )
        local_file_btn.clicked.connect(self._browse_local_file)

        file_layout = QHBoxLayout()
        file_layout.addWidget(self.f_local_file)
        file_layout.addWidget(local_file_btn)

        self.f_web_link = QLineEdit()
        self.f_web_link.setPlaceholderText("https://... (optional)")
        self.f_web_link.setText(self.data.get("web_link", ""))

        form.addRow("Number", self.f_number)
        form.addRow("Title", self.f_title)
        form.addRow("Date", self.f_date)
        form.addRow("Rating", self.f_rating)
        form.addRow("Review", self.f_review)
        form.addRow("Local File", file_layout)
        form.addRow("Web Link", self.f_web_link)
        layout.addLayout(form)

        # Image picker
        img_layout = QHBoxLayout()
        self._update_preview()
        img_layout.addWidget(self.img_preview)

        btn_v_layout = QVBoxLayout()
        browse_btn = QPushButton("📁 Browse Image")
        browse_btn.clicked.connect(self._browse)

        gen_btn = QPushButton("⚡ Gen Thumbnail")
        gen_btn.setStyleSheet(
            "background-color:#e67e22; color:white; font-weight:bold; padding: 4px 8px; border-radius: 4px;"
        )
        gen_btn.clicked.connect(self._generate_thumbnail)

        btn_v_layout.addWidget(browse_btn)
        btn_v_layout.addWidget(gen_btn)
        btn_v_layout.addStretch()
        img_layout.addLayout(btn_v_layout)
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

    def _browse_local_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Local Episode File",
            "",
            "All Files (*.*);;Videos (*.mp4 *.mkv *.avi *.mov *.webm);;Documents (*.pdf *.epub)",
        )
        if path:
            self.f_local_file.setText(path)

    def _generate_thumbnail(self):
        file_path = self.f_local_file.text().strip()
        if not file_path:
            QMessageBox.warning(
                self,
                "No Local File",
                "Please specify a valid Local File first to generate a thumbnail.",
            )
            return

        p = Path(file_path)
        if not p.exists():
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The local file at '{file_path}' does not exist.",
            )
            return

        suffix = p.suffix.lower()
        LISTING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        ep_id = self.data.get("id") or str(uuid.uuid4())
        dest_p = LISTING_IMAGES_DIR / f"ep_{ep_id}.png"

        # Image formats - shortcut direct copy
        if suffix in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
            try:
                shutil.copy2(file_path, dest_p)
                self.image_path = str(dest_p.absolute())
                self._update_preview()
                QMessageBox.information(
                    self, "Success", "Image set as thumbnail successfully!"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to set image: {e}")
            return

        # Video / PDF formats - selection dialog
        if suffix in (".pdf", ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v"):
            dlg = FrameSelectionDialog(file_path, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_image:
                if dlg.selected_image.save(str(dest_p.absolute())):
                    self.image_path = str(dest_p.absolute())
                    self._update_preview()
                    QMessageBox.information(
                        self,
                        "Success",
                        "Successfully saved selected representative thumbnail!",
                    )
                else:
                    QMessageBox.critical(
                        self, "Error", "Failed to save selected thumbnail image."
                    )
            return

        QMessageBox.warning(
            self,
            "Unsupported Format",
            "This file format is not supported for generating a thumbnail.",
        )

    def get_data(self) -> Dict[str, Any]:
        date_obj = self.f_date.date().toPython()
        return {
            "id": self.data.get("id") or str(uuid.uuid4()),
            "number": self.f_number.value(),
            "title": self.f_title.text().strip(),
            "date_watched": date_obj.isoformat(),  # pyrefly: ignore [missing-attribute]
            "rating": self.f_rating.value(),
            "review": self.f_review.toPlainText().strip(),
            "image_path": self.image_path,
            "local_file": self.f_local_file.text().strip(),
            "web_link": self.f_web_link.text().strip(),
        }
