"""Right-docked offline lesson shell loaded by Krita."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from krita import DockWidget, Krita
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .diagnostics import diagnose
from .engine_client import EngineClient
from .exercise import create_exercise_project
from .landmark_dialog import LandmarkDialog
from .progress_view import format_progress
from .redlines import accept_preview, reject_preview, render_review_redlines
from .settings import load_config, save_shortcuts, save_show_raw_measurements
from .shortcut_dialog import ShortcutDialog


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
        helpful_button = QPushButton("Advice: Helpful", container)
        helpful_button.clicked.connect(lambda checked=False: self._report_feedback("helpful"))
        unhelpful_button = QPushButton("Advice: Unhelpful", container)
        unhelpful_button.clicked.connect(lambda checked=False: self._report_feedback("unhelpful"))
        incorrect_button = QPushButton("Advice: Incorrect", container)
        incorrect_button.clicked.connect(lambda checked=False: self._report_feedback("incorrect"))
        not_applicable_button = QPushButton("Advice: Not Applicable", container)
        not_applicable_button.clicked.connect(
            lambda checked=False: self._report_feedback("not_applicable")
        )
        shortcut_button = QPushButton("Configure Shortcuts", container)
        shortcut_button.clicked.connect(self._configure_shortcuts)
        progress_heading = QLabel("Project Progress", container)
        self._progress_text = QLabel(
            "Create a portable exercise project to view progress.", container
        )
        self._progress_text.setWordWrap(True)
        config = load_config()
        self._raw_measurements = QCheckBox("Show raw normalized measurements", container)
        self._raw_measurements.setChecked(config["show_raw_measurements"])
        self._raw_measurements.toggled.connect(self._set_raw_measurements)
        self._feedback_history = QCheckBox("Keep advice-feedback edit history", container)
        self._feedback_note_limit = QSpinBox(container)
        self._feedback_note_limit.setRange(1, 100000)
        self._feedback_note_limit.setValue(2000)
        self._feedback_note_limit.setSuffix(" note characters")
        save_feedback_settings = QPushButton("Save Feedback Settings", container)
        save_feedback_settings.clicked.connect(self._save_feedback_policy)
        refresh_progress_button = QPushButton("Refresh Progress", container)
        refresh_progress_button.clicked.connect(self._refresh_progress)
        enable_progress_button = QPushButton("Enable Project Progress", container)
        enable_progress_button.clicked.connect(self._enable_progress)
        disable_progress_button = QPushButton("Disable & Clear Project Progress", container)
        disable_progress_button.clicked.connect(self._disable_progress)
        self._landmarks = None
        self._preview_layer = None
        self._project_directory = None
        self._attempt_id = None
        self._review_id = None
        self._pending_decision = None
        self._shortcuts = {}
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
        layout.addWidget(helpful_button)
        layout.addWidget(unhelpful_button)
        layout.addWidget(incorrect_button)
        layout.addWidget(not_applicable_button)
        layout.addWidget(shortcut_button)
        layout.addWidget(progress_heading)
        layout.addWidget(self._progress_text)
        layout.addWidget(self._raw_measurements)
        layout.addWidget(self._feedback_history)
        layout.addWidget(self._feedback_note_limit)
        layout.addWidget(save_feedback_settings)
        layout.addWidget(refresh_progress_button)
        layout.addWidget(enable_progress_button)
        layout.addWidget(disable_progress_button)
        layout.addWidget(self._action_status)
        layout.addWidget(status)
        layout.addWidget(diagnostics)
        layout.addStretch(1)
        scroll.setWidget(container)
        self.setWidget(scroll)
        self._apply_shortcuts(config["shortcuts"])

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
        self._refresh_progress()

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
        self._pending_decision = None
        suffix = (
            "\nNo correction layer was needed."
            if layer is None
            else "\nA locked tutor preview was added; explicitly accept or reject it."
        )
        self._action_status.setText("Review\n• " + "\n• ".join(explanations) + suffix)
        self._refresh_progress()

    def _refresh_progress(self) -> None:
        if self._project_directory is None:
            self._progress_text.setText("Create a portable exercise project to view progress.")
            return
        try:
            snapshot = EngineClient().project_progress_snapshot(
                "progress-" + str(uuid.uuid4()), self._project_directory
            )
            rendered = format_progress(snapshot, self._raw_measurements.isChecked())
        except (RuntimeError, TypeError, ValueError) as error:
            self._progress_text.setText(f"Progress unavailable: {error}")
            return
        self._progress_text.setText(rendered)
        policy = snapshot.get("feedback_policy", {})
        self._feedback_history.setChecked(policy.get("retain_revision_history", False))
        self._feedback_note_limit.setValue(policy.get("note_character_limit", 2000))

    def _set_raw_measurements(self, enabled) -> None:
        try:
            save_show_raw_measurements(bool(enabled))
        except ValueError as error:
            self._action_status.setText(f"Could not save progress display setting: {error}")
            return
        self._refresh_progress()

    def _report_feedback(self, rating) -> None:
        if None in (self._project_directory, self._attempt_id, self._review_id):
            self._action_status.setText("Request and save a project review before rating advice.")
            return
        note, accepted = QInputDialog.getMultiLineText(
            self,
            "Advice Feedback",
            f"Optional note (maximum {self._feedback_note_limit.value()} characters):",
        )
        if not accepted:
            self._action_status.setText("Advice feedback was not changed.")
            return
        note = note.strip() or None
        try:
            result = EngineClient().record_advice_feedback(
                "feedback-" + str(uuid.uuid4()),
                self._project_directory,
                self._attempt_id,
                self._review_id,
                rating,
                note,
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Could not save advice feedback: {error}")
            return
        state = "updated" if result.get("changed") else "unchanged"
        self._action_status.setText(f"Advice feedback {state}: {rating.replace('_', ' ')}.")
        self._refresh_progress()

    def _save_feedback_policy(self) -> None:
        if self._project_directory is None:
            self._action_status.setText("Create or bind a portable project first.")
            return
        try:
            EngineClient().configure_feedback_policy(
                "feedback-policy-" + str(uuid.uuid4()),
                self._project_directory,
                self._feedback_history.isChecked(),
                self._feedback_note_limit.value(),
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Could not save feedback settings: {error}")
            return
        self._action_status.setText("Project advice-feedback settings updated.")
        self._refresh_progress()

    def _disable_progress(self) -> None:
        if self._project_directory is None:
            self._action_status.setText("Create or bind a portable project first.")
            return
        choice = QMessageBox.warning(
            self,
            "Clear Learning Progress?",
            "Choose Yes to permanently clear this project's review history and disable "
            "learning-progress retention. Choose Cancel to keep it enabled.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if choice != QMessageBox.Yes:
            self._action_status.setText("Learning-progress retention remains enabled.")
            return
        try:
            EngineClient().configure_progress_retention(
                "retention-" + str(uuid.uuid4()),
                self._project_directory,
                False,
                clear_existing=True,
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Could not change progress retention: {error}")
            return
        self._action_status.setText(
            "Project learning progress was permanently cleared and retention disabled."
        )
        self._refresh_progress()

    def _enable_progress(self) -> None:
        if self._project_directory is None:
            self._action_status.setText("Create or bind a portable project first.")
            return
        try:
            EngineClient().configure_progress_retention(
                "retention-" + str(uuid.uuid4()), self._project_directory, True
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Could not change progress retention: {error}")
            return
        self._action_status.setText("Project learning-progress retention is enabled.")
        self._refresh_progress()

    def _accept_preview(self) -> None:
        if self._preview_layer is None:
            self._action_status.setText("There is no pending tutor preview to accept.")
            return
        if self._pending_decision not in (None, "accepted"):
            self._action_status.setText(
                "A rejected decision is awaiting persistence; retry Reject."
            )
            return
        if self._pending_decision is None:
            try:
                accept_preview(self._preview_layer)
            except (RuntimeError, ValueError) as error:
                self._action_status.setText(f"Could not accept preview: {error}")
                return
            self._pending_decision = "accepted"
        if not self._persist_decision("accepted"):
            return
        self._action_status.setText("Preview accepted as a locked tutor reference layer.")
        self._pending_decision = None
        self._preview_layer = None

    def _reject_preview(self) -> None:
        if self._preview_layer is None:
            self._action_status.setText("There is no pending tutor preview to reject.")
            return
        if self._pending_decision not in (None, "rejected"):
            self._action_status.setText(
                "An accepted decision is awaiting persistence; retry Accept."
            )
            return
        if self._pending_decision is None:
            try:
                reject_preview(self._preview_layer)
            except (RuntimeError, ValueError) as error:
                self._action_status.setText(f"Could not reject preview: {error}")
                return
            self._pending_decision = "rejected"
        if not self._persist_decision("rejected"):
            return
        self._pending_decision = None
        self._preview_layer = None
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

    def _configure_shortcuts(self) -> None:
        current = load_config()["shortcuts"]
        dialog = ShortcutDialog(current, self)
        if dialog.exec_() != dialog.Accepted:
            return
        try:
            save_shortcuts(dialog.shortcuts())
        except ValueError as error:
            self._action_status.setText(f"Could not save shortcuts: {error}")
            return
        self._apply_shortcuts(dialog.shortcuts())
        self._action_status.setText("Tutor shortcuts updated. Empty actions remain unassigned.")

    def _apply_shortcuts(self, shortcuts) -> None:
        for shortcut in self._shortcuts.values():
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self._shortcuts = {}
        handlers = {
            "review": self._request_review,
            "accept": self._accept_preview,
            "reject": self._reject_preview,
        }
        for action, sequence in shortcuts.items():
            if sequence:
                shortcut = QShortcut(QKeySequence(sequence), self)
                shortcut.activated.connect(handlers[action])
                self._shortcuts[action] = shortcut

    def canvasChanged(self, canvas) -> None:  # noqa: N802
        """Krita callback; this shell does not inspect the canvas."""
