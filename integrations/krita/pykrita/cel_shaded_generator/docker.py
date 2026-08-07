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

from .asymmetry_landmarks import AsymmetryLandmarkCollector, selected_asymmetry_stage
from .curriculum_content import adjacent_index, load_lessons, render_lesson_text
from .diagnostics import diagnose
from .engine_client import EngineClient
from .exercise import create_exercise_project
from .eye_landmarks import EyeLandmarkCollector, selected_eye_view
from .feature_landmarks import FeatureLandmarkCollector, selected_feature_view
from .landmark_dialog import LandmarkDialog
from .orientation_landmarks import (
    OrientationLandmarkCollector,
    selected_design_view,
    selected_orientation_view,
)
from .progress_view import format_progress
from .redlines import (
    accept_preview,
    map_review_redlines_to_matrix,
    map_review_redlines_to_sheet,
    reject_preview,
    render_review_redlines,
)
from .settings import load_config, save_shortcuts, save_show_raw_measurements
from .shortcut_dialog import ShortcutDialog
from .value_masks import MASK_SIDE, find_named_node, sampled_alpha_mask
from .variation_landmarks import VariationLandmarkCollector, selected_variation_stage


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
        pair_review_button = QPushButton("Review Front / Turned Design Pair", container)
        pair_review_button.clicked.connect(self._request_pair_review)
        feature_set_button = QPushButton("Review Complete Front / Turned Feature Set", container)
        feature_set_button.clicked.connect(self._request_feature_set_review)
        value_review_button = QPushButton("Review Binary Cel-Value Masks", container)
        value_review_button.clicked.connect(self._request_value_review)
        capstone_next_button = QPushButton("Run Next Capstone Review", container)
        capstone_next_button.clicked.connect(self._run_next_capstone_review)
        accept_button = QPushButton("Accept Preview", container)
        accept_button.clicked.connect(self._accept_preview)
        reject_button = QPushButton("Reject Preview", container)
        reject_button.clicked.connect(self._reject_preview)
        defer_button = QPushButton("Defer Preview Decision", container)
        defer_button.clicked.connect(self._defer_preview)
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
        self._identity_history = QCheckBox("Keep identity-card edit history", container)
        edit_identity_card = QPushButton("Create / Edit Identity Card", container)
        edit_identity_card.clicked.connect(self._edit_identity_card)
        save_identity_policy = QPushButton("Save Identity Card History Setting", container)
        save_identity_policy.clicked.connect(self._save_identity_card_policy)
        self._rationale_history = QCheckBox("Keep capstone rationale edit history", container)
        save_rationale_policy = QPushButton("Save Rationale History Setting", container)
        save_rationale_policy.clicked.connect(self._save_capstone_policy)
        edit_rationale = QPushButton("Edit Current Capstone Rationale", container)
        edit_rationale.clicked.connect(self._edit_capstone_rationale)
        refresh_progress_button = QPushButton("Refresh Progress", container)
        refresh_progress_button.clicked.connect(self._refresh_progress)
        enable_progress_button = QPushButton("Enable Project Progress", container)
        enable_progress_button.clicked.connect(self._enable_progress)
        disable_progress_button = QPushButton("Disable & Clear Project Progress", container)
        disable_progress_button.clicked.connect(self._disable_progress)
        self._landmarks = None
        self._orientation_view = None
        self._orientation_crop_index = None
        self._design_variant_id = None
        self._eye_stage = None
        self._feature_id = None
        self._feature_landmarks = {}
        self._asymmetry_stage = None
        self._asymmetry_intent = None
        self._asymmetry_landmarks = {}
        self._variation_stage = None
        self._variation_landmarks = {}
        self._identity_card = None
        self._pair_landmarks = {}
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
        layout.addWidget(pair_review_button)
        layout.addWidget(feature_set_button)
        layout.addWidget(value_review_button)
        layout.addWidget(capstone_next_button)
        layout.addWidget(accept_button)
        layout.addWidget(reject_button)
        layout.addWidget(defer_button)
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
        layout.addWidget(self._identity_history)
        layout.addWidget(edit_identity_card)
        layout.addWidget(save_identity_policy)
        layout.addWidget(self._rationale_history)
        layout.addWidget(save_rationale_policy)
        layout.addWidget(edit_rationale)
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
        self._design_variant_id = None
        self._eye_stage = None
        self._feature_id = None
        self._feature_landmarks = {}
        self._asymmetry_stage = None
        self._asymmetry_intent = None
        self._asymmetry_landmarks = {}
        self._variation_stage = None
        self._variation_landmarks = {}
        self._pair_landmarks = {}
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
        self._design_variant_id = None
        self._eye_stage = None
        self._feature_id = None
        self._asymmetry_stage = None
        self._asymmetry_intent = None
        self._variation_stage = None
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
        elif lesson["exercise_id"] == "anime-head-volume-jaw":
            try:
                view, crop_index, variant_id = selected_design_view(document.activeNode())
            except (AttributeError, ValueError) as error:
                self._action_status.setText(f"Select one cranial/jaw work layer: {error}")
                return
            confirmation = QMessageBox.question(
                self,
                "Confirm Selected Design",
                "Review only the active cranial/jaw construction layer?",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if confirmation != QMessageBox.Yes:
                self._action_status.setText("Selected-design review cancelled.")
                return
            self._orientation_view = view
            self._orientation_crop_index = crop_index
            self._design_variant_id = variant_id
            if view != "front":
                collector = OrientationLandmarkCollector(view)
            title = "Place " + view.replace("_", " ").title() + " Design Landmarks"
        elif lesson["exercise_id"] == "anime-head-eyes":
            try:
                view, stage, crop_index = selected_eye_view(document.activeNode())
            except (AttributeError, ValueError) as error:
                self._action_status.setText(f"Select one eye exercise layer: {error}")
                return
            confirmation = QMessageBox.question(
                self,
                "Confirm Selected Eye Study",
                "Review only the active eye exercise layer?",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if confirmation != QMessageBox.Yes:
                self._action_status.setText("Selected eye-study review cancelled.")
                return
            self._orientation_view = view
            self._orientation_crop_index = crop_index
            self._eye_stage = stage
            collector = EyeLandmarkCollector()
            title = "Place " + stage.replace("_", " ").title() + " Eye Landmarks"
        elif lesson["exercise_id"] == "anime-head-features":
            try:
                feature, view, crop_index = selected_feature_view(document.activeNode())
            except (AttributeError, ValueError) as error:
                self._action_status.setText(f"Select one feature exercise layer: {error}")
                return
            confirmation = QMessageBox.question(
                self,
                "Confirm Selected Feature Study",
                "Review only the active " + feature + " construction layer?",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if confirmation != QMessageBox.Yes:
                self._action_status.setText("Selected feature-study review cancelled.")
                return
            self._feature_id = feature
            self._orientation_view = view
            self._orientation_crop_index = crop_index
            collector = FeatureLandmarkCollector(feature, view)
            title = "Place " + feature.title() + " Review Landmarks"
        elif lesson["exercise_id"] == "anime-head-asymmetry":
            try:
                stage, crop_index, requires_intent = selected_asymmetry_stage(document.activeNode())
            except (AttributeError, ValueError) as error:
                self._action_status.setText(f"Select one controlled-asymmetry layer: {error}")
                return
            intent = self._collect_asymmetry_intent() if requires_intent else None
            if requires_intent and intent is None:
                self._action_status.setText("Intent labeling cancelled; no landmarks were changed.")
                return
            confirmation = QMessageBox.question(
                self,
                "Confirm Asymmetry Study",
                "Record only the active controlled-asymmetry layer?",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if confirmation != QMessageBox.Yes:
                self._action_status.setText("Controlled-asymmetry review cancelled.")
                return
            self._asymmetry_stage = stage
            self._asymmetry_intent = intent
            self._orientation_crop_index = crop_index
            collector = AsymmetryLandmarkCollector()
            title = "Place Controlled-Asymmetry Comparison Landmarks"
        elif lesson["exercise_id"] == "anime-head-variation":
            try:
                stage, crop_index = selected_variation_stage(document.activeNode())
            except (AttributeError, ValueError) as error:
                self._action_status.setText(f"Select one character-variation layer: {error}")
                return
            confirmation = QMessageBox.question(
                self,
                "Confirm Identity Study",
                "Record only the active character-variation layer?",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if confirmation != QMessageBox.Yes:
                self._action_status.setText("Character-variation review cancelled.")
                return
            self._variation_stage = stage
            self._orientation_crop_index = crop_index
            collector = VariationLandmarkCollector()
            title = "Place Identity Comparison Landmarks"
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
        if lesson["exercise_id"] == "anime-head-volume-jaw":
            key = "front" if self._orientation_view == "front" else "turned"
            self._pair_landmarks[key] = self._landmarks
            if self._design_variant_id != "selected_variant":
                self._pair_landmarks["variant_id"] = self._design_variant_id
        elif lesson["exercise_id"] == "anime-head-features":
            self._feature_landmarks[(self._orientation_view, self._feature_id)] = self._landmarks
        elif lesson["exercise_id"] == "anime-head-asymmetry":
            self._asymmetry_landmarks[self._asymmetry_stage] = {
                "landmarks": self._landmarks,
                "intent": self._asymmetry_intent,
            }
        elif lesson["exercise_id"] == "anime-head-variation":
            self._variation_landmarks[self._variation_stage] = self._landmarks
        self._action_status.setText(
            "Review landmarks recorded from the current projection. The artwork was not modified."
        )

    def _request_value_review(self) -> None:
        lesson = self._lessons[self._lesson_selector.currentIndex()]
        if lesson["exercise_id"] != "anime-head-cel-values":
            self._action_status.setText("Select the cel-value lesson before reviewing masks.")
            return
        document = Krita.instance().activeDocument()
        if document is None or self._project_directory is None or self._attempt_id is None:
            self._action_status.setText("Open the bound cel-value exercise project first.")
            return
        direction, accepted = QInputDialog.getItem(
            self,
            "Confirm Light Direction",
            "Declared light direction:",
            ["top left", "top", "top right", "left", "right"],
            0,
            False,
        )
        if not accepted:
            return
        hardness, accepted = QInputDialog.getItem(
            self,
            "Confirm Boundary",
            "Declared boundary hardness:",
            ["hard", "moderate"],
            0,
            False,
        )
        if not accepted:
            return
        root = document.rootNode()
        front_form = find_named_node(root, "02 Front Form-Shadow Mask")
        front_cast = find_named_node(root, "03 Front Cast-Shadow Mask")
        third = find_named_node(root, "04 Optional Third-Value Accent Mask")
        turned_form = find_named_node(root, "05 Right Three-Quarter Form-Shadow Mask")
        turned_cast = find_named_node(root, "06 Right Three-Quarter Cast-Shadow Mask")
        if any(node is None for node in (front_form, front_cast, turned_form, turned_cast)):
            self._action_status.setText("The required named form/cast mask layers were not found.")
            return
        try:
            front_form_mask = sampled_alpha_mask(front_form, 1, document.width(), document.height())
            front_cast_mask = sampled_alpha_mask(front_cast, 2, document.width(), document.height())
            turned_form_mask = sampled_alpha_mask(
                turned_form, 4, document.width(), document.height()
            )
            turned_cast_mask = sampled_alpha_mask(
                turned_cast, 5, document.width(), document.height()
            )
            third_mask = (
                sampled_alpha_mask(third, 3, document.width(), document.height())
                if third is not None
                else None
            )
            if third_mask is not None and not any(third_mask):
                third_mask = None
            request_id = str(uuid.uuid4())
            client = EngineClient()
            review = client.review_value_masks(
                request_id,
                front_form_mask,
                front_cast_mask,
                turned_form_mask,
                turned_cast_mask,
                MASK_SIDE,
                MASK_SIDE,
                direction.replace(" ", "_"),
                hardness,
                third_mask,
            )
            client.record_attempt_review(
                "record-" + review["id"],
                self._project_directory,
                self._attempt_id,
                review,
            )
        except (AttributeError, RuntimeError, ValueError) as error:
            self._action_status.setText("Value-mask review unavailable: " + str(error))
            return
        self._review_id = review["id"]
        self._action_status.setText(" ".join(review["explanations"]))
        self._refresh_progress()

    def _run_next_capstone_review(self) -> None:
        if self._project_directory is None or self._attempt_id is None:
            self._action_status.setText("Open the bound capstone project first.")
            return
        document = Krita.instance().activeDocument()
        if document is None:
            self._action_status.setText("Open the capstone document first.")
            return
        try:
            snapshot = EngineClient().project_progress_snapshot(
                str(uuid.uuid4()), self._project_directory
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText("Capstone plan unavailable: " + str(error))
            return
        dashboard = snapshot.get("capstone_dashboard", {})
        stage = dashboard.get("next_stage")
        if stage is None:
            self._action_status.setText(
                "All required capstone rubrics are resolved; completion remains your decision."
            )
            return
        layer = find_named_node(document.rootNode(), stage["layer_name"])
        if layer is None:
            self._action_status.setText(
                "Required capstone layer was not found: " + stage["layer_name"]
            )
            return
        confirmation = QMessageBox.question(
            self,
            "Confirm Next Capstone Review",
            "Select “" + stage["layer_name"] + "” for " + stage["stage_id"].replace("_", " ") + "?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if confirmation != QMessageBox.Yes:
            return
        document.setActiveNode(layer)
        candidates = [
            item
            for item in dashboard.get("import_candidates", [])
            if item["rubric_id"] == stage["rubric_id"]
        ]
        if not candidates:
            self._collect_fresh_capstone_review(stage, document, snapshot)
            return
        use_import = QMessageBox.question(
            self,
            "Import Compatible Evidence?",
            "Compatible prior evidence exists. Import the latest review instead of "
            "collecting fresh evidence?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if use_import != QMessageBox.Yes:
            self._collect_fresh_capstone_review(stage, document, snapshot)
            return
        decision, accepted = QInputDialog.getItem(
            self,
            "Capstone Import Decision",
            "Decision for this imported evidence:",
            ["accepted", "rejected", "deferred"],
            0,
            False,
        )
        if not accepted:
            return
        rationale, accepted = QInputDialog.getMultiLineText(
            self,
            "Capstone Import Rationale",
            "Explain why this earlier evidence remains applicable:",
        )
        if not accepted or not rationale.strip():
            self._action_status.setText("Import cancelled: a rationale is required.")
            return
        source = candidates[-1]
        try:
            EngineClient().import_compatible_capstone_review(
                str(uuid.uuid4()),
                self._project_directory,
                self._attempt_id,
                source["attempt_id"],
                source["review_id"],
                decision,
                rationale,
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText("Could not import capstone evidence: " + str(error))
            return
        self._action_status.setText("Compatible evidence imported with new capstone rationale.")
        self._refresh_progress()
        self._run_next_capstone_review()

    def _collect_fresh_capstone_review(self, stage, document, snapshot) -> None:
        try:
            if stage["stage_id"] == "front_structure":
                landmarks = self._capstone_landmarks(document, None, stage["layer_name"], 1)
                review = EngineClient().review_front_head(str(uuid.uuid4()), landmarks)
                crop_index = 1
            elif stage["stage_id"] == "turned_structure":
                collector = OrientationLandmarkCollector("right_three_quarter")
                landmarks = self._capstone_landmarks(document, collector, stage["layer_name"], 2)
                review = EngineClient().review_orientation_head(
                    str(uuid.uuid4()), "right_three_quarter", landmarks
                )
                crop_index = 2
            elif stage["stage_id"] == "identity_retention":
                card = snapshot.get("identity_card")
                if card is None:
                    raise ValueError("create the portable identity card before identity review")
                baseline = self._capstone_landmarks(
                    document,
                    VariationLandmarkCollector(),
                    "02 Front Construction",
                    1,
                )
                candidate = self._capstone_landmarks(
                    document,
                    VariationLandmarkCollector(),
                    stage["layer_name"],
                    2,
                )
                review = EngineClient().review_identity_comparison(
                    str(uuid.uuid4()), baseline, candidate, "selected_turned", card
                )
                crop_index = 2
            elif stage["stage_id"] == "expression_asymmetry":
                intent = self._collect_asymmetry_intent()
                if intent is None:
                    raise ValueError("expression intent is required")
                control = self._capstone_landmarks(
                    document,
                    AsymmetryLandmarkCollector(),
                    "02 Front Construction",
                    1,
                )
                candidate = self._capstone_landmarks(
                    document,
                    AsymmetryLandmarkCollector(),
                    stage["layer_name"],
                    3,
                )
                review = EngineClient().review_asymmetry_comparison(
                    str(uuid.uuid4()), control, candidate, "expression", intent
                )
                crop_index = 3
            else:
                review = self._capstone_value_review(document)
                crop_index = 3
        except (AttributeError, RuntimeError, ValueError) as error:
            self._action_status.setText("Fresh capstone review unavailable: " + str(error))
            return
        self._finalize_fresh_capstone_review(review, document, crop_index)

    def _capstone_landmarks(self, document, collector, layer_name, crop_index):
        layer = find_named_node(document.rootNode(), layer_name)
        if layer is None:
            raise ValueError("required capstone drawing layer is missing")
        document.setActiveNode(layer)
        dialog = LandmarkDialog(
            document,
            self,
            collector=collector,
            title="Capstone — " + layer_name,
            crop_index=crop_index,
        )
        if dialog.exec_() != dialog.Accepted:
            raise ValueError("landmark collection was cancelled")
        return dialog.landmarks()

    def _capstone_value_review(self, document):
        names = (
            "Capstone Front Form-Shadow Mask",
            "Capstone Front Cast-Shadow Mask",
            "Capstone Turned Form-Shadow Mask",
            "Capstone Turned Cast-Shadow Mask",
            "Capstone Optional Third-Value Accent Mask",
        )
        nodes = [find_named_node(document.rootNode(), name) for name in names]
        if any(node is None for node in nodes):
            raise ValueError("capstone value-mask layers are missing")
        direction, accepted = QInputDialog.getItem(
            self,
            "Confirm Capstone Light",
            "Declared light direction:",
            ["top left", "top", "top right", "left", "right"],
            0,
            False,
        )
        if not accepted:
            raise ValueError("light confirmation was cancelled")
        hardness, accepted = QInputDialog.getItem(
            self, "Confirm Boundary", "Boundary hardness:", ["hard", "moderate"], 0, False
        )
        if not accepted:
            raise ValueError("boundary confirmation was cancelled")
        masks = [sampled_alpha_mask(node, 3, document.width(), document.height()) for node in nodes]
        third = masks[4] if any(masks[4]) else None
        return EngineClient().review_value_masks(
            str(uuid.uuid4()),
            masks[0],
            masks[1],
            masks[2],
            masks[3],
            MASK_SIDE,
            MASK_SIDE,
            direction.replace(" ", "_"),
            hardness,
            third,
        )

    def _finalize_fresh_capstone_review(self, review, document, crop_index) -> None:
        client = EngineClient()
        client.record_attempt_review(
            "record-" + review["id"], self._project_directory, self._attempt_id, review
        )
        preview = render_review_redlines(
            document, map_review_redlines_to_matrix(review, crop_index)
        )
        decision, accepted = QInputDialog.getItem(
            self,
            "Capstone Review Decision",
            "Decision after inspecting the explanation and preview:",
            ["accepted", "rejected", "deferred"],
            0,
            False,
        )
        if not accepted:
            self._action_status.setText("Review saved with a pending decision.")
            self._refresh_progress()
            return
        rationale, accepted = QInputDialog.getMultiLineText(
            self, "Capstone Decision Rationale", "Explain this decision:"
        )
        if not accepted or not rationale.strip():
            self._action_status.setText("Review saved; a rationale is required to finalize it.")
            self._refresh_progress()
            return
        client.decide_attempt_review(
            "decide-" + review["id"],
            self._project_directory,
            self._attempt_id,
            review["id"],
            decision,
            rationale,
        )
        if preview is not None:
            if decision == "accepted":
                accept_preview(preview)
            else:
                reject_preview(preview)
        self._action_status.setText("Capstone review finalized; advancing to the next rubric.")
        self._refresh_progress()
        self._run_next_capstone_review()

    def _request_review(self) -> None:
        lesson = self._lessons[self._lesson_selector.currentIndex()]
        if self._landmarks is None:
            self._action_status.setText("Place all required review landmarks first.")
            return
        try:
            client = EngineClient()
            request_id = str(uuid.uuid4())
            if lesson["exercise_id"] == "anime-head-eyes":
                review = client.review_eye_pair(
                    request_id, self._orientation_view, self._eye_stage, self._landmarks
                )
            elif lesson["exercise_id"] == "anime-head-features":
                review = client.review_feature_study(
                    request_id, self._feature_id, self._orientation_view, self._landmarks
                )
            elif lesson["exercise_id"] == "anime-head-asymmetry":
                if self._asymmetry_stage == "front_control":
                    self._action_status.setText(
                        "Symmetric front control recorded. Select a later layer to compare it."
                    )
                    return
                control_stage = (
                    "turned_control" if self._asymmetry_stage == "transferred" else "front_control"
                )
                if control_stage not in self._asymmetry_landmarks:
                    self._action_status.setText(
                        "Record the required symmetric control landmarks before comparison."
                    )
                    return
                review = client.review_asymmetry_comparison(
                    request_id,
                    self._asymmetry_landmarks[control_stage]["landmarks"],
                    self._landmarks,
                    self._asymmetry_stage,
                    self._asymmetry_intent,
                )
            elif lesson["exercise_id"] == "anime-head-variation":
                if self._variation_stage == "baseline":
                    self._action_status.setText(
                        "Identity baseline recorded. Select a variant or reconstruction to compare."
                    )
                    return
                if self._identity_card is None:
                    self._action_status.setText(
                        "Create the portable five-to-eight-anchor identity card first."
                    )
                    return
                baseline_stage = (
                    "selected_front" if self._variation_stage == "selected_turned" else "baseline"
                )
                if baseline_stage not in self._variation_landmarks:
                    self._action_status.setText(
                        "Record the required identity baseline landmarks before comparison."
                    )
                    return
                review = client.review_identity_comparison(
                    request_id,
                    self._variation_landmarks[baseline_stage],
                    self._landmarks,
                    self._variation_stage,
                    self._identity_card,
                )
            elif lesson["exercise_id"] in {
                "anime-head-orientation",
                "anime-head-volume-jaw",
            } and self._orientation_view not in (None, "front"):
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
                lesson["exercise_id"] == "anime-head-eyes"
                and self._orientation_crop_index is not None
            ):
                renderable_review = map_review_redlines_to_sheet(
                    review, self._orientation_crop_index, cell_count=4
                )
            elif (
                lesson["exercise_id"] == "anime-head-features"
                and self._orientation_crop_index is not None
            ):
                renderable_review = map_review_redlines_to_matrix(
                    review, self._orientation_crop_index
                )
            elif (
                lesson["exercise_id"] == "anime-head-asymmetry"
                and self._orientation_crop_index is not None
            ):
                renderable_review = map_review_redlines_to_matrix(
                    review, self._orientation_crop_index
                )
            elif (
                lesson["exercise_id"] == "anime-head-variation"
                and self._orientation_crop_index is not None
            ):
                renderable_review = map_review_redlines_to_matrix(
                    review, self._orientation_crop_index
                )
            elif (
                lesson["exercise_id"]
                in {
                    "anime-head-orientation",
                    "anime-head-volume-jaw",
                }
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

    def _request_pair_review(self) -> None:
        lesson = self._lessons[self._lesson_selector.currentIndex()]
        if lesson["exercise_id"] != "anime-head-volume-jaw":
            self._action_status.setText("Paired review is available in the cranial/jaw lesson.")
            return
        missing = {"front", "turned", "variant_id"} - self._pair_landmarks.keys()
        if missing:
            self._action_status.setText(
                "Place landmarks on one front variant and the turned variant before paired review."
            )
            return
        if self._project_directory is None or self._attempt_id is None:
            self._action_status.setText("Create a portable exercise project before paired review.")
            return
        try:
            client = EngineClient()
            review = client.review_cranial_jaw_pair(
                str(uuid.uuid4()),
                self._pair_landmarks["variant_id"],
                self._pair_landmarks["front"],
                self._pair_landmarks["turned"],
            )
            client.record_attempt_review(
                "record-" + review["id"],
                self._project_directory,
                self._attempt_id,
                review,
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Paired review unavailable: {error}")
            return
        explanations = review.get("explanations", [])
        if not explanations:
            self._action_status.setText(
                "Paired review completed without an explanation; report this bug."
            )
            return
        self._review_id = review["id"]
        self._preview_layer = None
        self._pending_decision = None
        self._action_status.setText(
            "Front / turned consistency review\n• " + "\n• ".join(explanations)
        )
        self._refresh_progress()

    def _request_feature_set_review(self) -> None:
        lesson = self._lessons[self._lesson_selector.currentIndex()]
        if lesson["exercise_id"] != "anime-head-features":
            self._action_status.setText("Combined feature review is available in lesson five.")
            return
        required = {
            (view, feature)
            for view in ("front", "right_three_quarter")
            for feature in ("nose", "mouth", "ear")
        }
        if not required <= self._feature_landmarks.keys():
            self._action_status.setText(
                "Place landmarks on all six feature layers before combined review."
            )
            return
        if self._project_directory is None or self._attempt_id is None:
            self._action_status.setText("Create a portable exercise project first.")
            return
        front = {
            feature: self._feature_landmarks[("front", feature)]
            for feature in ("nose", "mouth", "ear")
        }
        turned = {
            feature: self._feature_landmarks[("right_three_quarter", feature)]
            for feature in ("nose", "mouth", "ear")
        }
        try:
            client = EngineClient()
            review = client.review_feature_set(str(uuid.uuid4()), front, turned)
            client.record_attempt_review(
                "record-" + review["id"],
                self._project_directory,
                self._attempt_id,
                review,
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Combined feature review unavailable: {error}")
            return
        explanations = review.get("explanations", [])
        if not explanations:
            self._action_status.setText(
                "Combined feature review returned no explanation; report this bug."
            )
            return
        self._review_id = review["id"]
        self._preview_layer = None
        self._pending_decision = None
        self._action_status.setText(
            "Front / turned feature consistency review\n• " + "\n• ".join(explanations)
        )
        self._refresh_progress()

    def _collect_asymmetry_intent(self):
        cause_label, accepted = QInputDialog.getItem(
            self,
            "Asymmetry Cause",
            "What causes the intended difference?",
            ["Anatomical / design", "Expression"],
            0,
            False,
        )
        if not accepted:
            return None
        side_label, accepted = QInputDialog.getItem(
            self,
            "Character Side",
            "Which character side carries the intended difference?",
            ["Character left", "Character right", "Bilateral"],
            0,
            False,
        )
        if not accepted:
            return None
        strength, accepted = QInputDialog.getItem(
            self,
            "Asymmetry Strength",
            "Choose the intended strength.",
            ["Subtle", "Medium", "Exaggerated"],
            0,
            False,
        )
        if not accepted:
            return None
        purpose, accepted = QInputDialog.getText(
            self,
            "Asymmetry Purpose",
            "State what this difference should communicate or preserve.",
        )
        if not accepted or not purpose.strip():
            return None
        return {
            "cause": cause_label.lower().replace(" / ", "_"),
            "side": side_label.lower().replace(" ", "_"),
            "strength": strength.lower(),
            "purpose": purpose.strip(),
        }

    def _edit_identity_card(self) -> None:
        if self._project_directory is None:
            self._action_status.setText(
                "Create a portable project before editing its identity card."
            )
            return
        name, accepted = QInputDialog.getText(self, "Identity Card", "Selected character name:")
        if not accepted or not name.strip():
            return
        count, accepted = QInputDialog.getInt(
            self, "Identity Card", "Number of structural anchors (5–8):", 6, 5, 8
        )
        if not accepted:
            return
        available = [
            "cranial_radius",
            "lower_face",
            "eye_span",
            "jaw_span",
            "mouth_span",
            "ear_height",
            "custom_anchor_1",
            "custom_anchor_2",
        ]
        anchors = []
        for index in range(count):
            key, accepted = QInputDialog.getItem(
                self,
                "Identity Anchor",
                f"Anchor {index + 1} normalized relationship:",
                available,
                0,
                False,
            )
            if not accepted:
                return
            available.remove(key)
            value, accepted = QInputDialog.getDouble(
                self,
                "Identity Anchor",
                "Normalized target value (0–1):",
                0.5,
                0.0,
                1.0,
                3,
            )
            if not accepted:
                return
            description, accepted = QInputDialog.getText(
                self,
                "Identity Anchor",
                "Describe why this relationship matters to identity:",
            )
            if not accepted or not description.strip():
                return
            anchors.append({"key": key, "value": value, "description": description.strip()})
        try:
            client = EngineClient()
            client.upsert_identity_card(
                str(uuid.uuid4()), self._project_directory, name.strip(), anchors
            )
            snapshot = client.project_progress_snapshot(str(uuid.uuid4()), self._project_directory)
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Could not save identity card: {error}")
            return
        self._identity_card = snapshot["identity_card"]
        self._action_status.setText(
            f"Identity card saved at revision {self._identity_card['revision']}."
        )

    def _save_identity_card_policy(self) -> None:
        if self._project_directory is None:
            self._action_status.setText("Create a portable project before changing card history.")
            return
        try:
            EngineClient().configure_identity_card_policy(
                str(uuid.uuid4()),
                self._project_directory,
                self._identity_history.isChecked(),
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Could not save identity-card policy: {error}")
            return
        self._action_status.setText("Identity-card history setting saved for this project.")
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
        self._rationale_history.setChecked(
            snapshot.get("capstone_policy", {}).get("retain_rationale_history", False)
        )
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

    def _save_capstone_policy(self) -> None:
        if self._project_directory is None:
            self._action_status.setText("Create a portable project before changing history.")
            return
        try:
            EngineClient().configure_capstone_policy(
                str(uuid.uuid4()),
                self._project_directory,
                self._rationale_history.isChecked(),
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText("Could not save rationale policy: " + str(error))
            return
        self._action_status.setText("Capstone rationale-history setting saved.")
        self._refresh_progress()

    def _edit_capstone_rationale(self) -> None:
        if None in (self._project_directory, self._attempt_id, self._review_id):
            self._action_status.setText("Select a persisted capstone review first.")
            return
        rationale, accepted = QInputDialog.getMultiLineText(
            self,
            "Edit Capstone Rationale",
            "Revise the rationale without changing its final decision:",
        )
        if not accepted or not rationale.strip():
            return
        try:
            EngineClient().revise_capstone_decision_rationale(
                str(uuid.uuid4()),
                self._project_directory,
                self._attempt_id,
                self._review_id,
                rationale,
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText("Could not revise rationale: " + str(error))
            return
        self._action_status.setText("Capstone rationale revised; the decision was unchanged.")
        self._refresh_progress()

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
        rationale = None
        lesson = self._lessons[self._lesson_selector.currentIndex()]
        if lesson["exercise_id"] == "anime-head-review":
            rationale, accepted = QInputDialog.getMultiLineText(
                self,
                "Capstone Decision Rationale",
                "Explain why you accepted, rejected, or deferred this suggestion:",
            )
            if not accepted or not rationale.strip():
                self._action_status.setText("Capstone decisions require a rationale.")
                return False
        try:
            EngineClient().decide_attempt_review(
                "decide-" + self._review_id,
                self._project_directory,
                self._attempt_id,
                self._review_id,
                decision,
                rationale,
            )
        except (RuntimeError, ValueError) as error:
            self._action_status.setText(f"Decision could not be saved: {error}")
            return False
        return True

    def _defer_preview(self) -> None:
        if self._preview_layer is None:
            self._action_status.setText("There is no pending tutor preview to defer.")
            return
        if not self._persist_decision("deferred"):
            return
        try:
            reject_preview(self._preview_layer)
        except (RuntimeError, ValueError) as error:
            self._action_status.setText("Decision saved, but preview cleanup failed: " + str(error))
            return
        self._preview_layer = None
        self._pending_decision = None
        self._action_status.setText("Preview decision deferred with its rationale recorded.")

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
