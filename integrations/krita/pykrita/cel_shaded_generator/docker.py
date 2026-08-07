"""Right-docked offline lesson shell loaded by Krita."""

from __future__ import annotations

import uuid
from pathlib import Path

from krita import DockWidget, Krita
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence, QPixmap
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
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

from .curriculum_content import adjacent_index, load_lessons, render_lesson_text
from .diagnostics import diagnose
from .engine_client import EngineClient
from .exercise import create_exercise_project
from .landmark_dialog import LandmarkDialog
from .orientation_landmarks import OrientationLandmarkCollector, selected_orientation_view
from .progress_view import format_progress
from .redlines import (
    accept_preview,
    map_review_redlines_to_sheet,
    reject_preview,
    render_review_redlines,
)
from .settings import load_config, save_shortcuts, save_show_raw_measurements
from .shortcut_dialog import ShortcutDialog


class LearningDocker(DockWidget):
    """Display the current locally packaged lesson without network access."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Cel-Shaded Learning Tutor")
        self._lessons = load_lessons(Path(__file__).parent / "content")
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QWidget(scroll)
        layout = QVBoxLayout(container)
        self._lesson_selector = QComboBox(container)
        self._lesson_selector.addItems([lesson["title"] for lesson in self._lessons])
        self._lesson_selector.currentIndexChanged.connect(self._select_lesson)
        previous_lesson = QPushButton("Previous Lesson", container)
        previous_lesson.clicked.connect(lambda checked=False: self._navigate_lesson(-1))
        next_lesson = QPushButton("Next Lesson", container)
        next_lesson.clicked.connect(lambda checked=False: self._navigate_lesson(1))
        self._lesson_title = QLabel(container)
        self._lesson_title.setWordWrap(True)
        self._lesson_body = QLabel(container)
        self._lesson_body.setWordWrap(True)
        self._diagram_selector = QComboBox(container)
        self._diagram_selector.currentIndexChanged.connect(self._select_diagram)
        self._lesson_diagram = QLabel(container)
        self._lesson_diagram.setAlignment(Qt.AlignCenter)
        self._lesson_complete = QCheckBox("I completed this exercise checklist", container)
        self._lesson_complete.toggled.connect(self._set_lesson_completion)
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
        self._orientation_view = None
        self._orientation_crop_index = None
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
        layout.addWidget(self._lesson_selector)
        layout.addWidget(previous_lesson)
        layout.addWidget(next_lesson)
        layout.addWidget(self._lesson_title)
        layout.addWidget(self._lesson_body)
        layout.addWidget(self._diagram_selector)
        layout.addWidget(self._lesson_diagram)
        layout.addWidget(self._lesson_complete)
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
        self._select_lesson(0)

    def _select_lesson(self, index) -> None:
        if not 0 <= index < len(self._lessons):
            return
        lesson = self._lessons[index]
        self._landmarks = None
        self._orientation_view = None
        self._orientation_crop_index = None
        self._lesson_title.setText(lesson["title"])
        self._lesson_body.setText(render_lesson_text(lesson))
        self._diagram_selector.blockSignals(True)
        self._diagram_selector.clear()
        self._diagram_selector.addItems(
            [Path(path).stem.replace("-", " ").title() for path in lesson.get("media", [])]
        )
        self._diagram_selector.blockSignals(False)
        self._diagram_selector.setVisible(bool(lesson.get("media")))
        self._lesson_diagram.setVisible(bool(lesson.get("media")))
        self._select_diagram(0)
        self._lesson_complete.blockSignals(True)
        self._lesson_complete.setChecked(False)
        self._lesson_complete.blockSignals(False)
        self._lesson_complete.setEnabled(False)
        if self._project_directory is not None:
            self._refresh_progress()

    def _select_diagram(self, index) -> None:
        lesson = self._lessons[self._lesson_selector.currentIndex()]
        media = lesson.get("media", [])
        if not 0 <= index < len(media):
            self._lesson_diagram.clear()
            return
        path = Path(__file__).parent / "content" / media[index]
        image = QPixmap(str(path))
        if image.isNull():
            self._lesson_diagram.setText("The packaged diagram could not be displayed.")
            return
        self._lesson_diagram.setPixmap(image.scaledToWidth(520, Qt.SmoothTransformation))

    def _navigate_lesson(self, offset) -> None:
        index = adjacent_index(self._lesson_selector.currentIndex(), len(self._lessons), offset)
        self._lesson_selector.setCurrentIndex(index)

    def _set_lesson_completion(self, completed) -> None:
        if self._project_directory is None or self._attempt_id is None:
            return
        try:
            EngineClient().set_attempt_completion(
                "completion-" + str(uuid.uuid4()),
                self._project_directory,
                self._attempt_id,
                bool(completed),
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Could not update exercise completion: {error}")
            self._lesson_complete.blockSignals(True)
            self._lesson_complete.setChecked(not completed)
            self._lesson_complete.blockSignals(False)
            return
        state = "complete" if completed else "incomplete"
        self._action_status.setText(
            f"Exercise explicitly marked {state}; review results did not change it automatically."
        )
        self._refresh_progress()

    def _create_exercise(self) -> None:
        lesson = self._lessons[self._lesson_selector.currentIndex()]
        directory = QFileDialog.getExistingDirectory(
            self, "Choose an Empty Portable Project Directory"
        )
        if not directory:
            self._action_status.setText("Project creation cancelled.")
            return
        attempt_id = str(uuid.uuid4())
        try:
            _, result = create_exercise_project(
                Krita.instance(), EngineClient(), directory, attempt_id, lesson["exercise_id"]
            )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            self._action_status.setText(f"Could not create exercise: {error}")
            return
        self._project_directory = directory
        self._attempt_id = result["attempt_id"]
        self._action_status.setText(
            "Portable project created for “"
            + lesson["title"]
            + "”. Draw on the named construction layer; tutor layout/feedback layers stay "
            "locked. Krita saves to artwork/attempt-001.kra."
        )
        self._refresh_progress()

    def _place_landmarks(self) -> None:
        lesson = self._lessons[self._lesson_selector.currentIndex()]
        document = Krita.instance().activeDocument()
        if document is None:
            self._action_status.setText("Open or create an exercise document first.")
            return
        collector = None
        crop_index = None
        title = None
        self._orientation_view = None
        if lesson["exercise_id"] == "anime-head-orientation":
            try:
                view, crop_index = selected_orientation_view(document.activeNode())
            except (AttributeError, ValueError) as error:
                self._action_status.setText(f"Select one orientation work layer: {error}")
                return
            confirmation = QMessageBox.question(
                self,
                "Confirm Selected Head",
                "Review only the active “" + view.replace("_", " ") + "” construction layer?",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if confirmation != QMessageBox.Yes:
                self._action_status.setText("Selected-head review cancelled.")
                return
            self._orientation_view = view
            self._orientation_crop_index = crop_index
            if view != "front":
                collector = OrientationLandmarkCollector(view)
            title = "Place " + view.replace("_", " ").title() + " Review Landmarks"
        dialog = LandmarkDialog(
            document,
            self,
            collector=collector,
            title=title,
            crop_index=crop_index,
        )
        if dialog.exec_() != dialog.Accepted:
            self._action_status.setText("Landmark placement cancelled; no review was requested.")
            return
        self._landmarks = dialog.landmarks()
        self._action_status.setText(
            "Nine landmarks recorded from the current projection. Engine review and redline "
            "rendering are the next step; artwork was not modified."
        )

    def _request_review(self) -> None:
        lesson = self._lessons[self._lesson_selector.currentIndex()]
        if self._landmarks is None:
            self._action_status.setText("Place all nine review landmarks first.")
            return
        try:
            client = EngineClient()
            request_id = str(uuid.uuid4())
            if lesson["exercise_id"] == "anime-head-orientation" and self._orientation_view not in (
                None,
                "front",
            ):
                review = client.review_orientation_head(
                    request_id, self._orientation_view, self._landmarks
                )
            else:
                review = client.review_front_head(request_id, self._landmarks)
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
            renderable_review = review
            if (
                lesson["exercise_id"] == "anime-head-orientation"
                and self._orientation_crop_index is not None
            ):
                renderable_review = map_review_redlines_to_sheet(
                    review, self._orientation_crop_index
                )
            layer = (
                render_review_redlines(document, renderable_review)
                if document is not None
                else None
            )
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
        selected_exercise = self._lessons[self._lesson_selector.currentIndex()]["exercise_id"]
        selected_attempt = next(
            (
                attempt
                for exercise in snapshot.get("exercises", [])
                if exercise.get("exercise_id") == selected_exercise
                for attempt in exercise.get("attempts", [])
                if attempt.get("attempt_id") == self._attempt_id
            ),
            None,
        )
        self._lesson_complete.blockSignals(True)
        self._lesson_complete.setChecked(
            selected_attempt is not None and selected_attempt.get("completed_at") is not None
        )
        self._lesson_complete.blockSignals(False)
        self._lesson_complete.setEnabled(selected_attempt is not None)

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
