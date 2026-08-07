"""Right-docked offline lesson shell loaded by Krita."""

from __future__ import annotations

import json
from pathlib import Path

from krita import DockWidget, Krita
from PyQt5.QtWidgets import QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from .diagnostics import diagnose
from .exercise import create_exercise_document
from .landmark_dialog import LandmarkDialog


class LearningDocker(DockWidget):
    """Display the current locally packaged lesson without network access."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Cel-Shaded Learning Tutor")
        lesson_path = Path(__file__).parent / "content" / "lesson.json"
        lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QWidget(scroll)
        layout = QVBoxLayout(container)
        title = QLabel(lesson["title"], container)
        title.setWordWrap(True)
        body = QLabel(lesson["summary"], container)
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        for step in lesson["steps"]:
            heading = QLabel(step["title"], container)
            explanation = QLabel(step["explanation"], container)
            heading.setWordWrap(True)
            explanation.setWordWrap(True)
            layout.addWidget(heading)
            layout.addWidget(explanation)
        checklist = QLabel(
            "Completion checklist\n• " + "\n• ".join(lesson["completion_criteria"]), container
        )
        checklist.setWordWrap(True)
        practice = QLabel("Practice\n" + lesson["practice_prompt"], container)
        practice.setWordWrap(True)
        create_button = QPushButton("Create Exercise Document", container)
        create_button.clicked.connect(self._create_exercise)
        landmark_button = QPushButton("Place Review Landmarks", container)
        landmark_button.clicked.connect(self._place_landmarks)
        self._landmarks = None
        self._action_status = QLabel(
            "Create an unsaved 1600 × 2000 exercise with separate construction, artwork, "
            "and tutor-feedback layers.",
            container,
        )
        self._action_status.setWordWrap(True)
        status = QLabel("Review and redlining arrive in the next A2 slice.", container)
        status.setWordWrap(True)
        report = diagnose(Krita.instance().version())
        diagnostics = QLabel("Diagnostics: " + " ".join(report.messages), container)
        diagnostics.setWordWrap(True)
        layout.addWidget(checklist)
        layout.addWidget(practice)
        layout.addWidget(create_button)
        layout.addWidget(landmark_button)
        layout.addWidget(self._action_status)
        layout.addWidget(status)
        layout.addWidget(diagnostics)
        layout.addStretch(1)
        scroll.setWidget(container)
        self.setWidget(scroll)

    def _create_exercise(self) -> None:
        try:
            create_exercise_document(Krita.instance())
        except (RuntimeError, TypeError) as error:
            self._action_status.setText(f"Could not create exercise: {error}")
            return
        self._action_status.setText(
            "Exercise created. Draw light construction on ‘Construction Guides’; reserve "
            "‘Artwork’ for deliberate lines. Save the document when ready."
        )

    def _place_landmarks(self) -> None:
        document = Krita.instance().activeDocument()
        if document is None:
            self._action_status.setText("Open or create an exercise document first.")
            return
        dialog = LandmarkDialog(document, self)
        if dialog.exec_() != dialog.Accepted:
            self._action_status.setText("Landmark placement cancelled; no review was requested.")
            return
        self._landmarks = dialog.landmarks()
        self._action_status.setText(
            "Nine landmarks recorded from the current projection. Engine review and redline "
            "rendering are the next step; artwork was not modified."
        )

    def canvasChanged(self, canvas) -> None:  # noqa: N802
        """Krita callback; this shell does not inspect the canvas."""
