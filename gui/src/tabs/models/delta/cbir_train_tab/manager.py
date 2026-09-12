"""``CBIRTrainTab`` -- composed from controllers (#544)."""

from __future__ import annotations

import threading
from typing import Any, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QLineEdit, QWidget

from ._browsers import CBIRTrainBrowsersController
from ._config import CBIRTrainConfigController
from ._index_builder import CBIRTrainIndexController
from ._loss_toggle import CBIRTrainLossToggleController
from ._telemetry_slots import CBIRTrainTelemetryController
from ._training_worker import CBIRTrainWorkerController
from ._ui_builder import CBIRTrainUIBuilder


class CBIRTrainTab(QWidget):
    """Training UI for fine-tuning a CBIR embedding model.

    Follows the same ``collect()`` / ``set_config()`` / ``get_default_config()``
    contract as the other ``UnifiedTrainTab`` children so the parent can save
    and restore session settings.
    """

    # Signals emitted from the background thread (thread-safe)
    sig_log = Signal(str)
    sig_metrics = Signal(dict)
    sig_epoch = Signal(int, dict)
    sig_done = Signal(str, str)  # (status: "ok"|"error"|"cancel", message)
    sig_index_progress = Signal(int, int)  # (n_done, n_total)
    sig_index_done = Signal(str, str)  # (status, message)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._train_thread: Optional[threading.Thread] = None
        self._index_thread: Optional[threading.Thread] = None

        # Composed controllers
        self.ui_builder = CBIRTrainUIBuilder(self)
        self.telemetry_controller = CBIRTrainTelemetryController(self)
        self.loss_controller = CBIRTrainLossToggleController(self)
        self.browsers_controller = CBIRTrainBrowsersController(self)
        self.training_controller = CBIRTrainWorkerController(self)
        self.index_controller = CBIRTrainIndexController(self)
        self.config_controller = CBIRTrainConfigController(self)

        self._init_ui()
        self.sig_log.connect(self._on_log)
        self.sig_metrics.connect(self._on_metrics)
        self.sig_epoch.connect(self._on_epoch)
        self.sig_done.connect(self._on_done)
        self.sig_index_progress.connect(self._on_index_progress)
        self.sig_index_done.connect(self._on_index_done)

    # --- Facade delegation ---
    # UI Builder
    def _init_ui(self) -> None:
        self.ui_builder.init_ui()

    @staticmethod
    def _make_metric_label(title: str, value: str) -> QLabel:
        return CBIRTrainUIBuilder._make_metric_label(title, value)

    # Browsers
    def _browse_dir(self, line_edit: QLineEdit) -> None:
        self.browsers_controller._browse_dir(line_edit)

    def _browse_checkpoint(self) -> None:
        self.browsers_controller._browse_checkpoint()

    # Loss toggle
    def _on_loss_changed(self, idx: int) -> None:
        self.loss_controller._on_loss_changed(idx)

    # Telemetry slots
    def _on_log(self, msg: str) -> None:
        self.telemetry_controller._on_log(msg)

    def _on_metrics(self, m: dict) -> None:
        self.telemetry_controller._on_metrics(m)

    def _on_epoch(self, epoch: int, m: dict) -> None:
        self.telemetry_controller._on_epoch(epoch, m)

    def _on_done(self, status: str, msg: str) -> None:
        self.telemetry_controller._on_done(status, msg)

    def _on_index_progress(self, done: int, total: int) -> None:
        self.telemetry_controller._on_index_progress(done, total)

    def _on_index_done(self, status: str, msg: str) -> None:
        self.telemetry_controller._on_index_done(status, msg)

    # Training worker
    def _start_training(self) -> None:
        self.training_controller._start_training()

    def _cancel_training(self) -> None:
        self.training_controller._cancel_training()

    # Index builder
    def _start_build_index(self) -> None:
        self.index_controller._start_build_index()

    # Config
    def collect(self) -> dict[str, Any]:
        return self.config_controller.collect()

    def set_config(self, cfg: dict[str, Any]) -> None:
        self.config_controller.set_config(cfg)

    def get_default_config(self) -> dict[str, Any]:
        return self.config_controller.get_default_config()


__all__ = ["CBIRTrainTab"]
