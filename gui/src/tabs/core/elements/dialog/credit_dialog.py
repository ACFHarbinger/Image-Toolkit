import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from gui.src.styles import SHARED_BUTTON_STYLE
from gui.src.tabs.core.elements.dialog.common.base_sub_item_dialog import BaseSubItemDialog
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)


class _CreditDialog(BaseSubItemDialog):
    def __init__(self, credit_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__("Credit / Work Details", parent)
        self.data = credit_data or {}
        self._item_id = self.data.get("id") or str(uuid.uuid4())
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

    def _listing_image_basename(self, source_path: str) -> Optional[str]:
        suffix = Path(source_path).suffix.lower() or ".png"
        return f"cr_{self._item_id}{suffix}"

    def get_data(self) -> Dict[str, Any]:
        return {
            "id": self._item_id,
            "title": self.f_title.text().strip(),
            "role": self.f_role.text().strip(),
            "year": self.f_year.value(),
            "rating": self.f_rating.value(),
            "notes": self.f_notes.toPlainText().strip(),
            "image_path": self.image_path,
        }
