from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from gui.src.constants.listings import ENTRY_TYPES
from gui.src.theming.theme_api import qss


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
        self.setStyleSheet(qss("recommendation_dialog"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("🌟 Recommend Content")
        header.setStyleSheet(qss("recommendation_title"))
        layout.addWidget(header)

        desc = QLabel(
            "Describe what you're looking for. Fill in keyword fields, the prompt, or both.\n"
            "When both are provided, results are fused with Reciprocal Rank Fusion."
        )
        desc.setStyleSheet(qss("recommendation_desc"))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(qss("recommendation_separator"))
        layout.addWidget(sep)

        # Structured filters
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)

        type_label = QLabel("Type:")
        type_label.setStyleSheet(qss("recommendation_form_label"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["All Types"] + ENTRY_TYPES)
        form.addRow(type_label, self.type_combo)

        genres_label = QLabel("Genres:")
        genres_label.setStyleSheet(qss("recommendation_form_label"))
        self.genres_edit = QLineEdit()
        self.genres_edit.setPlaceholderText("e.g. Action, Sci-Fi, Psychological")
        form.addRow(genres_label, self.genres_edit)

        tags_label = QLabel("Tags:")
        tags_label.setStyleSheet(qss("recommendation_form_label"))
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("e.g. time-travel, mecha, philosophical")
        form.addRow(tags_label, self.tags_edit)

        entities_label = QLabel("Entities:")
        entities_label.setStyleSheet(qss("recommendation_form_label"))
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
        cancel_btn.setStyleSheet(qss("database_dialog_cancel_btn"))
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)

        run_btn = QPushButton("🌟 Run Recommendation")
        run_btn.setFixedWidth(180)
        run_btn.setStyleSheet(qss("recommendation_run_btn"))
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
