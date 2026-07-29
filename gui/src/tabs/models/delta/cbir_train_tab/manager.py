"""``CBIRTrainTab`` -- composed from per-concern mixins."""

from __future__ import annotations

import threading
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from ._browsers import _BrowsersMixin
from ._config import _ConfigMixin
from ._index_builder import _IndexBuilderMixin
from ._loss_toggle import _LossToggleMixin
from ._telemetry_slots import _TelemetrySlotsMixin
from ._training_worker import _TrainingWorkerMixin
from ._ui_builder import _UIBuilderMixin


class CBIRTrainTab(
    _UIBuilderMixin,
    _TelemetrySlotsMixin,
    _LossToggleMixin,
    _BrowsersMixin,
    _TrainingWorkerMixin,
    _IndexBuilderMixin,
    _ConfigMixin,
    QWidget,
):
    """Training UI for fine-tuning a CBIR embedding model.

    Follows the same ``collect()`` / ``set_config()`` / ``get_default_config()``
    contract as the other ``UnifiedTrainTab`` children so the parent can save
    and restore session settings.
    """

    # Signals emitted from the background thread (thread-safe)
    sig_log = Signal(str)
    sig_metrics = Signal(dict)
    sig_epoch = Signal(int, dict)
    sig_done = Signal(str, str)          # (status: "ok"|"error"|"cancel", message)
    sig_index_progress = Signal(int, int)  # (n_done, n_total)
    sig_index_done = Signal(str, str)    # (status, message)

    def __init__(self) -> None:
        super().__init__()
        self._train_thread: Optional[threading.Thread] = None
        self._index_thread: Optional[threading.Thread] = None
        self._init_ui()
        self.sig_log.connect(self._on_log)
        self.sig_metrics.connect(self._on_metrics)
        self.sig_epoch.connect(self._on_epoch)
        self.sig_done.connect(self._on_done)
        self.sig_index_progress.connect(self._on_index_progress)
        self.sig_index_done.connect(self._on_index_done)


__all__ = ["CBIRTrainTab"]
