"""
StitchFeedbackTab — RLHF feedback collection and agent training UI.

Workflow
--------
1. Load a stitched panorama with "Load Image".
2. Drag rectangles on the canvas to mark flaw regions; assign flaw type
   and severity from the right panel.
3. Set the overall quality rating with the slider.
4. Click "Submit Feedback" to persist the record.
5. Once enough feedback is collected, click "Train Reward Model" to
   fine-tune the CNN reward model.
6. Click "Fine-tune DRL Agent" to update the registration agent using
   the reward model as the reward signal.
"""

from __future__ import annotations

import os
from typing import List, Optional

import cv2
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QColor, QFont, QPixmap, QImage
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from ...helpers.stitch.annotation_canvas import AnnotationCanvas
from backend.src.core.anim.rlhf.feedback_store import (
    FLAW_TYPES,
    FeedbackStore,
    StitchAnnotation,
)

# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

class _RewardModelTrainWorker(QObject):
    progress = Signal(int, int, float)    # epoch, total, val_loss
    finished = Signal(str)                # summary message
    error = Signal(str)

    def __init__(self, store_path: str, model_path: str, epochs: int):
        super().__init__()
        self._store_path = store_path
        self._model_path = model_path
        self._epochs = epochs

    @Slot()
    def run(self):
        try:
            from backend.src.core.anim.rlhf import FeedbackStore, train_reward_model
            store = FeedbackStore(path=self._store_path)
            n = store.count()
            if n == 0:
                self.error.emit("No feedback records found — submit some ratings first.")
                return
            model = train_reward_model(
                store,
                model_path=self._model_path if self._model_path else None,
                epochs=self._epochs,
                progress_cb=lambda ep, tot, loss: self.progress.emit(ep, tot, loss),
            )
            self.finished.emit(
                f"Reward model trained on {n} samples. "
                f"Saved to {model._path}."
            )
        except Exception as exc:
            self.error.emit(str(exc))


class _DRLFineTuneWorker(QObject):
    progress = Signal(int, int, float)   # episode, total, reward
    finished = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        image_paths: List[str],
        model_path: str,
        episodes: int,
        agent_path: str,
    ):
        super().__init__()
        self._image_paths = image_paths
        self._model_path = model_path
        self._episodes = episodes
        self._agent_path = agent_path

    @Slot()
    def run(self):
        try:
            import torch
            import numpy as _np
            from backend.src.core.anim.rlhf import StitchRewardModel, fine_tune_drl_agent
            from backend.src.core.anim.mfsr.drl_registration import RegistrationAgent

            reward_model = StitchRewardModel(
                model_path=self._model_path if self._model_path else None
            )
            agent = RegistrationAgent()
            # Reload previously saved agent weights if available
            if self._agent_path and os.path.exists(self._agent_path):
                state = torch.load(
                    self._agent_path, map_location=agent.device, weights_only=True
                )
                agent.online.load_state_dict(state)
                agent.target.load_state_dict(state)
                agent._trained = True

            # Build frame pairs from the image list (consecutive pairs)
            pairs = []
            for path in self._image_paths:
                img = cv2.imread(path, cv2.IMREAD_COLOR)
                if img is not None:
                    pairs.append(img)
            frame_pairs = list(zip(pairs, pairs[1:]))
            if not frame_pairs:
                self.error.emit("Need at least 2 valid images to form training pairs.")
                return

            fine_tune_drl_agent(
                agent,
                reward_model,
                frame_pairs,
                episodes=self._episodes,
                progress_cb=lambda ep, tot, sc: self.progress.emit(ep, tot, sc),
            )

            # Save updated agent weights
            if self._agent_path:
                import pathlib
                pathlib.Path(self._agent_path).parent.mkdir(parents=True, exist_ok=True)
                torch.save(agent.online.state_dict(), self._agent_path)

            self.finished.emit(
                f"DRL agent fine-tuned on {len(frame_pairs)} frame pairs "
                f"({self._episodes} episodes each)."
            )
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Main tab
# ---------------------------------------------------------------------------

class StitchFeedbackTab(QWidget):
    """RLHF feedback collection and agent training tab."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._store = FeedbackStore()
        self._image_path: Optional[str] = None
        self._image_bgr = None  # numpy BGR
        self._training_thread: Optional[QThread] = None
        self._drl_thread: Optional[QThread] = None
        self._training_worker = None
        self._drl_worker = None

        self._build_ui()
        self._refresh_feedback_count()

    # ----------------------------------------------------------------- UI build

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # ── Left: annotation canvas ──────────────────────────────────────────
        self._canvas = AnnotationCanvas()
        self._canvas.annotation_added.connect(self._on_annotation_drawn)
        splitter.addWidget(self._canvas)

        # ── Right: controls ──────────────────────────────────────────────────
        ctrl_container = QWidget()
        ctrl_container.setMinimumWidth(320)
        ctrl_container.setMaximumWidth(400)
        ctrl_scroll = QScrollArea()
        ctrl_scroll.setWidgetResizable(True)
        ctrl_scroll.setWidget(ctrl_container)
        splitter.addWidget(ctrl_scroll)
        splitter.setSizes([700, 330])

        ctrl = QVBoxLayout(ctrl_container)
        ctrl.setSpacing(8)

        # ── Image loading ────────────────────────────────────────────────────
        load_grp = QGroupBox("Stitched Image")
        load_lay = QVBoxLayout(load_grp)
        self._load_btn = QPushButton("Load Image…")
        self._load_btn.clicked.connect(self._load_image)
        self._image_label = QLabel("No image loaded")
        self._image_label.setWordWrap(True)
        self._image_label.setStyleSheet("color: #888; font-size: 11px;")
        load_lay.addWidget(self._load_btn)
        load_lay.addWidget(self._image_label)
        ctrl.addWidget(load_grp)

        # ── Overall rating ───────────────────────────────────────────────────
        rating_grp = QGroupBox("Overall Quality Rating")
        rating_lay = QVBoxLayout(rating_grp)
        self._rating_slider = QSlider(Qt.Horizontal)
        self._rating_slider.setRange(0, 100)
        self._rating_slider.setValue(80)
        self._rating_slider.setTickInterval(10)
        self._rating_slider.setTickPosition(QSlider.TicksBelow)
        self._rating_val_label = QLabel("8.0 / 10")
        self._rating_slider.valueChanged.connect(
            lambda v: self._rating_val_label.setText(f"{v / 10:.1f} / 10")
        )
        rating_lay.addWidget(self._rating_slider)
        rating_lay.addWidget(self._rating_val_label)
        ctrl.addWidget(rating_grp)

        # ── Annotation controls ──────────────────────────────────────────────
        ann_grp = QGroupBox("Annotation")
        ann_lay = QVBoxLayout(ann_grp)

        flaw_row = QHBoxLayout()
        flaw_row.addWidget(QLabel("Flaw type:"))
        self._flaw_combo = QComboBox()
        self._flaw_combo.addItems(FLAW_TYPES)
        self._flaw_combo.currentTextChanged.connect(self._canvas.set_active_flaw_type)
        flaw_row.addWidget(self._flaw_combo)
        ann_lay.addLayout(flaw_row)

        sev_row = QHBoxLayout()
        sev_row.addWidget(QLabel("Severity:"))
        self._severity_slider = QSlider(Qt.Horizontal)
        self._severity_slider.setRange(0, 100)
        self._severity_slider.setValue(50)
        self._severity_val_label = QLabel("0.5")
        self._severity_slider.valueChanged.connect(self._on_severity_changed)
        sev_row.addWidget(self._severity_slider)
        sev_row.addWidget(self._severity_val_label)
        ann_lay.addLayout(sev_row)

        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText("Optional description…")
        ann_lay.addWidget(self._desc_edit)

        self._mark_btn = QPushButton("Mark Region (draw)")
        self._mark_btn.setCheckable(True)
        self._mark_btn.toggled.connect(self._on_mark_toggled)
        ann_lay.addWidget(self._mark_btn)

        self._ann_list = QListWidget()
        self._ann_list.setMaximumHeight(140)
        ann_lay.addWidget(self._ann_list)

        remove_btn = QPushButton("Remove Selected Annotation")
        remove_btn.clicked.connect(self._remove_selected_annotation)
        ann_lay.addWidget(remove_btn)

        clear_btn = QPushButton("Clear All Annotations")
        clear_btn.clicked.connect(self._clear_annotations)
        ann_lay.addWidget(clear_btn)

        ctrl.addWidget(ann_grp)

        # ── Submit ───────────────────────────────────────────────────────────
        self._submit_btn = QPushButton("Submit Feedback")
        self._submit_btn.setEnabled(False)
        self._submit_btn.clicked.connect(self._submit_feedback)
        ctrl.addWidget(self._submit_btn)

        self._feedback_count_label = QLabel("Feedback records: 0")
        self._feedback_count_label.setStyleSheet("color: #888; font-size: 11px;")
        ctrl.addWidget(self._feedback_count_label)

        # ── Reward model training ────────────────────────────────────────────
        rm_grp = QGroupBox("Reward Model Training")
        rm_lay = QVBoxLayout(rm_grp)

        epoch_row = QHBoxLayout()
        epoch_row.addWidget(QLabel("Epochs:"))
        self._epochs_spin = QSpinBox()
        self._epochs_spin.setRange(1, 200)
        self._epochs_spin.setValue(20)
        epoch_row.addWidget(self._epochs_spin)
        rm_lay.addLayout(epoch_row)

        self._train_rm_btn = QPushButton("Train Reward Model")
        self._train_rm_btn.clicked.connect(self._train_reward_model)
        rm_lay.addWidget(self._train_rm_btn)
        ctrl.addWidget(rm_grp)

        # ── DRL fine-tuning ──────────────────────────────────────────────────
        drl_grp = QGroupBox("DRL Agent Fine-tuning (RLHF)")
        drl_lay = QVBoxLayout(drl_grp)

        self._drl_dir_edit = QLineEdit()
        self._drl_dir_edit.setPlaceholderText("Directory of source frames…")
        drl_dir_btn = QPushButton("Browse…")
        drl_dir_btn.clicked.connect(self._browse_drl_dir)
        drl_dir_row = QHBoxLayout()
        drl_dir_row.addWidget(self._drl_dir_edit)
        drl_dir_row.addWidget(drl_dir_btn)
        drl_lay.addLayout(drl_dir_row)

        drl_ep_row = QHBoxLayout()
        drl_ep_row.addWidget(QLabel("Episodes per pair:"))
        self._drl_episodes_spin = QSpinBox()
        self._drl_episodes_spin.setRange(1, 100)
        self._drl_episodes_spin.setValue(12)
        drl_ep_row.addWidget(self._drl_episodes_spin)
        drl_lay.addLayout(drl_ep_row)

        self._drl_train_btn = QPushButton("Fine-tune DRL Agent")
        self._drl_train_btn.clicked.connect(self._fine_tune_drl)
        drl_lay.addWidget(self._drl_train_btn)
        ctrl.addWidget(drl_grp)

        # ── Log ──────────────────────────────────────────────────────────────
        log_grp = QGroupBox("Log")
        log_lay = QVBoxLayout(log_grp)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(120)
        font = QFont("Monospace", 9)
        self._log.setFont(font)
        log_lay.addWidget(self._log)
        ctrl.addWidget(log_grp)

        ctrl.addStretch()

    # ----------------------------------------------------------------- slots

    @Slot()
    def _load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Stitched Panorama",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        self._image_path = path
        self._image_label.setText(os.path.basename(path))
        # Load via QPixmap for display; keep BGR for feedback store
        self._image_bgr = cv2.imread(path, cv2.IMREAD_COLOR)
        pixmap = QPixmap(path)
        self._canvas.set_image(pixmap)
        self._canvas.clear_annotations()
        self._ann_list.clear()
        self._submit_btn.setEnabled(True)
        self._log_msg(f"Loaded: {path}")

    @Slot(bool)
    def _on_mark_toggled(self, checked: bool):
        self._canvas.set_annotation_mode(checked)
        if checked:
            self._mark_btn.setText("Mark Region — click & drag on image")
        else:
            self._mark_btn.setText("Mark Region (draw)")

    @Slot(int)
    def _on_severity_changed(self, value: int):
        sev = value / 100.0
        self._severity_val_label.setText(f"{sev:.2f}")
        self._canvas.set_active_severity(sev)

    @Slot(float, float, float, float)
    def _on_annotation_drawn(self, x, y, w, h):
        # Disable draw mode after each annotation so the user must re-enable
        self._mark_btn.setChecked(False)
        ann = self._canvas.annotations[-1]
        ann.description = self._desc_edit.text()
        item = QListWidgetItem(
            f"{ann.flaw_type}  [{x:.2f},{y:.2f}  {w:.2f}×{h:.2f}]  s={ann.severity:.2f}"
        )
        self._ann_list.addItem(item)
        self._desc_edit.clear()
        self._log_msg(
            f"Annotation added: {ann.flaw_type} at "
            f"({x:.2f},{y:.2f}) size {w:.2f}×{h:.2f}, severity {ann.severity:.2f}"
        )

    @Slot()
    def _remove_selected_annotation(self):
        row = self._ann_list.currentRow()
        if row < 0:
            return
        self._ann_list.takeItem(row)
        self._canvas.remove_annotation(row)

    @Slot()
    def _clear_annotations(self):
        self._canvas.clear_annotations()
        self._ann_list.clear()

    @Slot()
    def _submit_feedback(self):
        if not self._image_path:
            return
        rating = self._rating_slider.value() / 10.0
        canvas_anns = self._canvas.annotations
        store_anns = [
            StitchAnnotation(
                x=a.x, y=a.y, w=a.w, h=a.h,
                flaw_type=a.flaw_type,
                severity=a.severity,
                description=a.description,
            )
            for a in canvas_anns
        ]
        fb = self._store.add_from_image(
            image_path=self._image_path,
            overall_rating=rating,
            annotations=store_anns,
        )
        self._log_msg(
            f"Feedback saved — rating={rating:.1f}, "
            f"{len(store_anns)} annotations, hash={fb.image_hash[:8]}…"
        )
        self._refresh_feedback_count()

    @Slot()
    def _train_reward_model(self):
        if self._training_thread is not None and self._training_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Reward model training is already in progress.")
            return
        self._train_rm_btn.setEnabled(False)
        self._log_msg("Starting reward model training…")

        worker = _RewardModelTrainWorker(
            store_path=str(self._store.path),
            model_path="",
            epochs=self._epochs_spin.value(),
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_rm_progress)
        worker.finished.connect(self._on_rm_finished)
        worker.error.connect(self._on_rm_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(lambda: self._train_rm_btn.setEnabled(True))

        self._training_thread = thread
        self._training_worker = worker
        thread.start()

    @Slot(int, int, float)
    def _on_rm_progress(self, ep: int, total: int, loss: float):
        self._log_msg(f"  [RM] Epoch {ep}/{total}  val_loss={loss:.5f}")

    @Slot(str)
    def _on_rm_finished(self, msg: str):
        self._log_msg(f"[RM] Done — {msg}")

    @Slot(str)
    def _on_rm_error(self, msg: str):
        self._log_msg(f"[RM] ERROR — {msg}")

    @Slot()
    def _browse_drl_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Frame Directory", "",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if d:
            self._drl_dir_edit.setText(d)

    @Slot()
    def _fine_tune_drl(self):
        if self._drl_thread is not None and self._drl_thread.isRunning():
            QMessageBox.warning(self, "Busy", "DRL fine-tuning is already in progress.")
            return
        frame_dir = self._drl_dir_edit.text().strip()
        if not frame_dir or not os.path.isdir(frame_dir):
            QMessageBox.warning(self, "No directory", "Select a frame directory first.")
            return

        from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS
        image_paths = sorted([
            os.path.join(frame_dir, f)
            for f in os.listdir(frame_dir)
            if os.path.splitext(f)[1].lower() in SUPPORTED_IMG_FORMATS
        ])
        if len(image_paths) < 2:
            QMessageBox.warning(self, "Too few images", "Need at least 2 images.")
            return

        from pathlib import Path
        agent_path = str(
            Path.home() / ".config" / "image-toolkit" / "drl_agent.pt"
        )
        self._drl_train_btn.setEnabled(False)
        self._log_msg(
            f"Fine-tuning DRL agent on {len(image_paths)} frames "
            f"({self._drl_episodes_spin.value()} ep/pair)…"
        )

        worker = _DRLFineTuneWorker(
            image_paths=image_paths,
            model_path="",
            episodes=self._drl_episodes_spin.value(),
            agent_path=agent_path,
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_drl_progress)
        worker.finished.connect(self._on_drl_finished)
        worker.error.connect(self._on_drl_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(lambda: self._drl_train_btn.setEnabled(True))

        self._drl_thread = thread
        self._drl_worker = worker
        thread.start()

    @Slot(int, int, float)
    def _on_drl_progress(self, ep: int, total: int, score: float):
        self._log_msg(f"  [DRL] Episode {ep}/{total}  reward_score={score:.4f}")

    @Slot(str)
    def _on_drl_finished(self, msg: str):
        self._log_msg(f"[DRL] Done — {msg}")

    @Slot(str)
    def _on_drl_error(self, msg: str):
        self._log_msg(f"[DRL] ERROR — {msg}")

    # ----------------------------------------------------------------- helpers

    def _log_msg(self, text: str) -> None:
        self._log.append(text)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    def _refresh_feedback_count(self) -> None:
        try:
            n = self._store.count()
        except Exception:
            n = 0
        self._feedback_count_label.setText(f"Feedback records: {n}")


__all__ = ["StitchFeedbackTab"]
