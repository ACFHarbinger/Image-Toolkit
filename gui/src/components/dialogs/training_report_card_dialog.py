"""#746: the training report card — the three-question summary shown after
a successful training run (Qwen's proposal §4.2). Non-modal by design: it
is a summary panel, not a blocking question."""
from __future__ import annotations

from backend.src.core.training_report import (
    STATUS_BAD,
    STATUS_GOOD,
    STATUS_INFO,
    STATUS_WARN,
    ReportCard,
)
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

_STATUS_COLORS = {
    STATUS_GOOD: "#3a9d6e",
    STATUS_WARN: "#c9a227",
    STATUS_BAD: "#c0392b",
    STATUS_INFO: "#8a8a8a",
}
_STATUS_DOTS = {STATUS_GOOD: "●", STATUS_WARN: "●", STATUS_BAD: "●", STATUS_INFO: "○"}


class TrainingReportCardDialog(QDialog):
    """Renders a ReportCard: one row per verdict plus the suggestion banner."""

    def __init__(self, card: ReportCard, *, run_dir: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Training Report Card")
        self.setModal(False)
        self._run_dir = run_dir

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        title = QLabel("Training Report Card")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        root.addWidget(title)

        for verdict in card.verdicts:
            root.addLayout(self._row(verdict.question, verdict))

        line = QLabel("—" * 24)
        root.addWidget(line)
        suggestion = QLabel("What to try next")
        suggestion.setStyleSheet("font-weight: bold;")
        root.addWidget(suggestion)
        root.addLayout(self._row("", card.suggestion))

        buttons = QHBoxLayout()
        buttons.addStretch()
        if run_dir:
            open_btn = QPushButton("Open Run Folder")
            open_btn.setToolTip(run_dir)
            open_btn.clicked.connect(self._open_run_folder)
            buttons.addWidget(open_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setDefault(True)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

    def _row(self, question: str, verdict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        dot = QLabel(_STATUS_DOTS.get(verdict.status, "○"))
        color = _STATUS_COLORS.get(verdict.status, _STATUS_COLORS[STATUS_INFO])
        dot.setStyleSheet(f"color: {color}; font-size: 16px;")
        dot.setToolTip(verdict.status)
        row.addWidget(dot)

        text = QVBoxLayout()
        text.setSpacing(0)
        if question:
            heading = QLabel(f"<b>{question}</b> {verdict.headline}")
            heading.setWordWrap(True)
            text.addWidget(heading)
        else:
            heading = QLabel(verdict.headline)
            heading.setWordWrap(True)
            text.addWidget(heading)
        if verdict.detail:
            detail = QLabel(verdict.detail)
            detail.setWordWrap(True)
            detail.setStyleSheet("color: #8a8a8a;")
            text.addWidget(detail)
        row.addLayout(text, stretch=1)
        return row

    def _open_run_folder(self) -> None:
        if self._run_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._run_dir))
