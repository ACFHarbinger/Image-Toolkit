"""Explicit, sequential one-field experiments from a completed LoRA run."""
from __future__ import annotations

import threading
from pathlib import Path

from middleware.src.comfy_matrix import gpu_lease, try_admit
from middleware.src.core import training_experiments as experiments
from middleware.src.core.gpu_vram_estimate import estimate_job_gb
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from gui.src.helpers.base import BaseQThreadWorker
from gui.src.helpers.worker_retention import retain_until_stopped

OWNER = "training-experiment"


class ExperimentWorker(BaseQThreadWorker):
    changed = Signal(object)

    def __init__(self, source: str, field=None, values=None, seed=42):
        super().__init__()
        self.source, self.field, self.values, self.seed = source, field, values, seed
        self.cancelled = threading.Event()
        self.folder = None

    def _execute(self):
        if self.field is None:
            return experiments.source_details(self.source)
        try:
            root = Path.home() / "Downloads/Data/Tests/dl-experiments"
            self.folder = experiments.prepare_experiment(
                self.source, self.field, self.values, self.seed, root, self.cancelled.is_set,
            )
            def update(folder):
                self.changed.emit((folder, experiments.curves(Path(folder))))
            result = experiments.run_experiment(self.folder, self.cancelled, update)
            return result
        finally:
            gpu_lease.release(OWNER)


class TrainingExperimentDialog(QDialog):
    def __init__(self, run_dir: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Experiment from this run")
        self.resize(900, 650)
        self._source = run_dir
        self._details = None
        self._worker = None
        self._error = False
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.field = QComboBox()
        self.field.addItems(list(experiments.FIELDS))
        self.values = QLineEdit("5e-5, 1e-4")
        self.seed = QSpinBox()
        self.seed.setRange(0, 2**31 - 1)
        self.seed.setValue(42)
        form.addRow("Vary one field", self.field)
        form.addRow("Values (2–6, comma-separated)", self.values)
        form.addRow("Shared seed", self.seed)
        layout.addLayout(form)
        self.estimate = QLabel("Reading source run…")
        self.estimate.setWordWrap(True)
        layout.addWidget(self.estimate)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        from gui.src.components.dialogs.adapter_rank_chart_dialog import _Canvas
        self.canvas, self.figure = _Canvas.new(self)
        layout.addWidget(self.canvas, 1)
        buttons = QHBoxLayout()
        self.launch = QPushButton("Launch sequential experiment…")
        self.launch.setEnabled(False)
        self.cancel = QPushButton("Cancel experiment")
        self.cancel.setEnabled(False)
        buttons.addWidget(self.launch)
        buttons.addWidget(self.cancel)
        layout.addLayout(buttons)
        self.launch.clicked.connect(self._launch)
        self.cancel.clicked.connect(self._cancel)
        self.field.currentTextChanged.connect(self._preview)
        self.values.textChanged.connect(self._preview)
        self._loader = ExperimentWorker(run_dir)
        self._loader.finished.connect(self._loaded)
        self._loader.error.connect(self._failed)
        retain_until_stopped(self._loader)
        self._loader.start()

    @Slot(object)
    def _loaded(self, details):
        if isinstance(details, dict):
            self._details = details
            self._preview()

    def _preview(self, *_):
        if self._details is None or self._worker is not None:
            return
        try:
            values = experiments.parse_values(self.field.currentText(), self.values.text())
            self.estimate.setText(experiments.estimate(self._details, self.field.currentText(), values) +
                                  " Dataset/captions are copied once; model revision, prompts and seed are fixed. "
                                  "The source uses all images for training, with no validation split. "
                                  "These are new runs; the source run is not a seeded control.")
            self.launch.setEnabled(True)
        except ValueError as exc:
            self.estimate.setText(str(exc))
            self.launch.setEnabled(False)

    def _launch(self):
        if self._worker is not None:
            return
        values = experiments.parse_values(self.field.currentText(), self.values.text())
        if QMessageBox.question(self, "Launch experiment", self.estimate.text() + "\n\nStart these runs?") != QMessageBox.StandardButton.Yes:
            return
        record = (self._details or {}).get("record") or {}
        config = record.get("config") if isinstance(record.get("config"), dict) else {}
        refusal = try_admit(
            OWNER,
            estimated_gb=estimate_job_gb(
                OWNER,
                model_id=record.get("model_id") or config.get("model_id"),
                rank=config.get("rank", 4),
                batch_size=config.get("batch_size", 1),
            ),
        )
        if refusal:
            QMessageBox.warning(self, "GPU busy", refusal)
            return
        worker = ExperimentWorker(self._source, self.field.currentText(), values, self.seed.value())
        self._worker = worker
        self.destroyed.connect(lambda *_args, flag=worker.cancelled: flag.set())
        self._error = False
        for control in (self.launch, self.field, self.values, self.seed):
            control.setEnabled(False)
        self.cancel.setEnabled(True)
        self.status.setText("Copying inputs and freezing the base-model revision…")
        worker.changed.connect(self._changed)
        worker.error.connect(self._failed)
        worker.finished.connect(self._done)
        retain_until_stopped(worker)
        try:
            worker.start()
        except Exception:
            gpu_lease.release(OWNER)
            self._worker = None
            raise

    @Slot(object)
    def _changed(self, payload):
        folder, series = payload
        self.status.setText(f"Experiment: {folder}")
        self.figure.clear()
        if series:
            axes = self.figure.subplots(1, len(series), sharex=True, sharey=True, squeeze=False)[0]
            for axis, run in zip(axes, series, strict=True):
                points = run["points"]
                if points:
                    axis.plot([p[0] for p in points], [p[1] for p in points])
                axis.set_title(f"{self.field.currentText()}={run['value']:g}\n{run['status']}", fontsize=9)
                axis.set_xlabel("Optimizer step")
                axis.grid(True, alpha=.2)
            axes[0].set_ylabel("Raw training loss")
            self.figure.tight_layout()
        self.canvas.draw()

    @Slot(object)
    def _done(self, result):
        self.cancel.setEnabled(False)
        if isinstance(result, dict):
            self.status.setText(f"Experiment {result['status']}. Results: {self._worker.folder}")
        # Keep the worker reference until dialog disposal; one experiment per dialog.

    @Slot(object)
    def _failed(self, error):
        self._error = True
        self.status.setText(f"Experiment unavailable: {error}")

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancelled.set()
            self.status.setText("Cancelling; waiting for the active child to exit…")

    def closeEvent(self, event):  # noqa: N802
        self._cancel()
        super().closeEvent(event)

    def reject(self):
        self._cancel()
        super().reject()
