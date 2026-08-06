"""Right-docked offline lesson shell loaded by Krita."""

from __future__ import annotations

import json
from pathlib import Path

from krita import DockWidget
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget


class LearningDocker(DockWidget):
    """Display the current locally packaged lesson without network access."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Cel-Shaded Learning Tutor")
        lesson_path = Path(__file__).parent / "content" / "lesson.json"
        lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
        container = QWidget(self)
        layout = QVBoxLayout(container)
        title = QLabel(lesson["title"], container)
        title.setWordWrap(True)
        body = QLabel(lesson["summary"], container)
        body.setWordWrap(True)
        status = QLabel("Placeholder lesson — drawing review is not implemented yet.", container)
        status.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(status)
        layout.addStretch(1)
        self.setWidget(container)

    def canvasChanged(self, canvas) -> None:  # noqa: N802
        """Krita callback; this shell does not inspect the canvas."""
