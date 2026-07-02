from typing import Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QFrame,
    QComboBox,
)

from gui.src.constants.listings import ENTRY_TYPES


class _RecommendationDialog(QDialog):
    """
    Dialog for specifying content recommendation criteria.

    Provides structured filters (Type, Genres, Tags, Entities) for
    sparse keyword matching and a free-form natural language prompt
    for dense semantic search.  When both are filled, results are
    fused via Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌟 Content Recommendation")
        self.setMinimumSize(560, 540)
        self.setStyleSheet(
            "QDialog { background: #1e1a2e; color: white; }"
            "QLabel { color: #ce93d8; font-weight: bold; font-size: 12px; }"
            "QLineEdit, QTextEdit {"
            "  background: #2c2f33; color: white;"
            "  border: 1px solid #7b1fa2; border-radius: 4px; padding: 4px;"
            "}"
            "QComboBox {"
            "  background: #2c2f33; color: white;"
            "  border: 1px solid #7b1fa2; border-radius: 4px; padding: 4px;"
            "}"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #2c2f33; color: white; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("🌟 Recommend Content")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #ce93d8;")
        layout.addWidget(header)

        desc = QLabel(
            "Describe what you're looking for. Fill in keyword fields, the prompt, or both.\n"
            "When both are provided, results are fused with Reciprocal Rank Fusion."
        )
        desc.setStyleSheet("color: #aaa; font-size: 11px; font-weight: normal;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #4f545c;")
        layout.addWidget(sep)

        # Structured filters
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)

        type_label = QLabel("Type:")
        type_label.setStyleSheet("color: #ce93d8; font-weight: bold;")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["All Types"] + ENTRY_TYPES)
        form.addRow(type_label, self.type_combo)

        genres_label = QLabel("Genres:")
        genres_label.setStyleSheet("color: #ce93d8; font-weight: bold;")
        self.genres_edit = QLineEdit()
        self.genres_edit.setPlaceholderText("e.g. Action, Sci-Fi, Psychological")
        form.addRow(genres_label, self.genres_edit)

        tags_label = QLabel("Tags:")
        tags_label.setStyleSheet("color: #ce93d8; font-weight: bold;")
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("e.g. time-travel, mecha, philosophical")
        form.addRow(tags_label, self.tags_edit)

        entities_label = QLabel("Entities:")
        entities_label.setStyleSheet("color: #ce93d8; font-weight: bold;")
        self.entities_edit = QLineEdit()
        self.entities_edit.setPlaceholderText("e.g. Makoto Shinkai, MAPPA, Yoko Taro")
        form.addRow(entities_label, self.entities_edit)

        layout.addLayout(form)

        # Natural language prompt
        prompt_label = QLabel("✏ Natural Language Prompt:")
        layout.addWidget(prompt_label)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText(
            "e.g. A dark sci-fi anime with deep philosophical themes, featuring complex "
            "female protagonists in a dystopian future that questions what it means to be human…"
        )
        self.prompt_edit.setMinimumHeight(110)
        self.prompt_edit.setMaximumHeight(160)
        layout.addWidget(self.prompt_edit)

        # Buttons
        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(90)
        cancel_btn.setStyleSheet(
            "QPushButton { background:#2f3136; color:white; border:1px solid #4f545c;"
            " border-radius:4px; padding:6px; font-weight:bold; }"
            "QPushButton:hover { background:#4f545c; }"
        )
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)

        run_btn = QPushButton("🌟 Run Recommendation")
        run_btn.setFixedWidth(180)
        run_btn.setStyleSheet(
            "QPushButton { background:#7b1fa2; color:white; border:none;"
            " border-radius:4px; padding:6px; font-weight:bold; }"
            "QPushButton:hover { background:#9c27b0; }"
            "QPushButton:pressed { background:#6a1b9a; }"
        )
        run_btn.clicked.connect(self.accept)
        run_btn.setDefault(True)
        btns.addWidget(run_btn)

        layout.addLayout(btns)

    def get_inputs(self) -> Dict[str, Any]:
        return {
            "type": self.type_combo.currentText(),
            "genres": self.genres_edit.text().strip(),
            "tags": self.tags_edit.text().strip(),
            "entities": self.entities_edit.text().strip(),
            "prompt": self.prompt_edit.toPlainText().strip(),
        }
