"""Right-docked offline lesson shell loaded by Krita."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from krita import DockWidget, Krita
from PyQt5.QtWidgets import QFileDialog, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from .diagnostics import diagnose
from .engine_client import EngineClient
from .exercise import create_exercise_project
from .landmark_dialog import LandmarkDialog
from .redlines import accept_preview, reject_preview, render_review_redlines


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
        review_button = QPushButton("Request Deterministic Review", container)
        review_button.clicked.connect(self._request_review)
        accept_button = QPushButton("Accept Preview", container)
        accept_button.clicked.connect(self._accept_preview)
        reject_button = QPushButton("Reject Preview", container)
        reject_button.clicked.connect(self._reject_preview)
        self._landmarks = None
        self._preview_layer = None
        self._project_directory = None
        self._attempt_id = None
        self._review_id = None
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
        layout.addWidget(review_button)
        layout.addWidget(accept_button)
        layout.addWidget(reject_button)
        layout.addWidget(self._action_status)
        layout.addWidget(status)
        layout.addWidget(diagnostics)
        layout.addStretch(1)
        scroll.setWidget(container)
        self.setWidget(scroll)

    def _create_exercise(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Choose an Empty Portable Project Directory"
        )
        if not directory:
            self._action_status.setText("Project creation cancelled.")
            return
        attempt_id = str(uuid.uuid4())
        try:
            _, result = create_exercise_project(
                Krita.instance(), EngineClient(), directory, attempt_id
            )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            self._action_status.setText(f"Could not create exercise: {error}")
            return
        self._project_directory = directory
        self._attempt_id = result["attempt_id"]
        self._action_status.setText(
            "Portable project created. Draw light construction on ‘Construction Guides’; "
            "reserve ‘Artwork’ for deliberate lines. Krita saves to artwork/attempt-001.kra."
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

    def _request_review(self) -> None:
        if self._landmarks is None:
            self._action_status.setText("Place all nine review landmarks first.")
            return
        try:
            review = EngineClient().review_front_head(str(uuid.uuid4()), self._landmarks)
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Review unavailable: {error}")
            return
        explanations = review.get("explanations", [])
        if not explanations:
            self._action_status.setText("Review completed without an explanation; report this bug.")
            return
        if self._project_directory is None or self._attempt_id is None:
            self._action_status.setText("Review completed, but no portable project is bound.")
            return
        try:
            EngineClient().record_attempt_review(
                "record-" + review["id"], self._project_directory, self._attempt_id, review
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Review completed but could not be saved: {error}")
            return
        self._review_id = review["id"]
        document = Krita.instance().activeDocument()
        try:
            layer = render_review_redlines(document, review) if document is not None else None
        except (RuntimeError, TypeError, ValueError) as error:
            self._action_status.setText(
                "Review completed, but redlines could not be rendered: " + str(error)
            )
            return
        self._preview_layer = layer if review.get("suggestions") else None
        suffix = (
            "\nNo correction layer was needed."
            if layer is None
            else "\nA locked tutor preview was added; explicitly accept or reject it."
        )
        self._action_status.setText("Review\n• " + "\n• ".join(explanations) + suffix)

    def _accept_preview(self) -> None:
        if self._preview_layer is None:
            self._action_status.setText("There is no pending tutor preview to accept.")
            return
        try:
            changed = accept_preview(self._preview_layer)
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Could not accept preview: {error}")
            return
        if changed:
            if not self._persist_decision("accepted"):
                return
            self._action_status.setText("Preview accepted as a locked tutor reference layer.")
        self._preview_layer = None

    def _reject_preview(self) -> None:
        if self._preview_layer is None:
            self._action_status.setText("There is no pending tutor preview to reject.")
            return
        try:
            reject_preview(self._preview_layer)
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Could not reject preview: {error}")
            return
        self._preview_layer = None
        if not self._persist_decision("rejected"):
            return
        self._action_status.setText("Preview rejected and removed; artist layers were unchanged.")

    def _persist_decision(self, decision) -> bool:
        if None in (self._project_directory, self._attempt_id, self._review_id):
            self._action_status.setText(
                "Decision could not be saved: review project state is missing."
            )
            return False
        try:
            EngineClient().decide_attempt_review(
                "decide-" + self._review_id,
                self._project_directory,
                self._attempt_id,
                self._review_id,
                decision,
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Decision could not be saved: {error}")
            return False
        return True

    def canvasChanged(self, canvas) -> None:  # noqa: N802
        """Krita callback; this shell does not inspect the canvas."""
