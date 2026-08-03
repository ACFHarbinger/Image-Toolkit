"""Typing-only host protocol for ``CBIRTrainTab``'s mixins.

Declares the widgets/signals/threads each mixin assumes the composed host
class provides, plus the cross-mixin methods they call on ``self``, so mypy
can type-check each mixin file in isolation without false ``attr-defined``
errors. Never instantiated -- see ``manager.CBIRTrainTab`` for the real
composition.
"""

from __future__ import annotations

import threading
from typing import Optional, Protocol

from PySide6.QtCore import SignalInstance
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextEdit,
)

from ..delta.cbir_train_tab._sparkline import _SparkLine


class CBIRTrainTabHostProtocol(Protocol):
    # Dataset / architecture / loss / training widgets (built in _UIBuilderMixin)
    _img_dir: QLineEdit
    _out_dir: QLineEdit
    _val_split: QDoubleSpinBox
    _backbone: QComboBox
    _embed_dim: QComboBox
    _proj_layers: QSpinBox
    _freeze_epochs: QSpinBox
    _image_size: QComboBox
    _loss_fn: QComboBox
    _temperature: QDoubleSpinBox
    _margin: QDoubleSpinBox
    _jitter: QDoubleSpinBox
    _epochs: QSpinBox
    _batch_size: QSpinBox
    _lr: QDoubleSpinBox
    _bb_lr_scale: QDoubleSpinBox
    _warmup: QSpinBox
    _workers: QSpinBox
    _amp: QCheckBox

    # Index-builder widgets
    _ckpt_path: QLineEdit
    _index_img_dir: QLineEdit
    _index_out_dir: QLineEdit
    _btn_build_index: QPushButton
    _index_progress: QProgressBar

    # Telemetry / training-control widgets
    _btn_start: QPushButton
    _btn_cancel: QPushButton
    _epoch_progress: QProgressBar
    _loss_chart: _SparkLine
    _recall_label: QLabel
    _lbl_best_r1: QLabel
    _lbl_epoch_loss: QLabel
    _lbl_lr_now: QLabel
    _log_box: QTextEdit
    _best_r1: float

    # Background-thread handles (manager.__init__)
    _train_thread: Optional[threading.Thread]
    _index_thread: Optional[threading.Thread]

    # Signals (declared on CBIRTrainTab)
    sig_log: SignalInstance
    sig_metrics: SignalInstance
    sig_epoch: SignalInstance
    sig_done: SignalInstance
    sig_index_progress: SignalInstance
    sig_index_done: SignalInstance

    # Cross-mixin methods
    def collect(self) -> dict: ...
    def _browse_dir(self, line_edit: QLineEdit) -> None: ...
    def _browse_checkpoint(self) -> None: ...
    def _on_loss_changed(self, idx: int) -> None: ...
    def _start_training(self) -> None: ...
    def _cancel_training(self) -> None: ...
    def _start_build_index(self) -> None: ...
    def _on_log(self, msg: str) -> None: ...
    def _make_metric_label(self, title: str, value: str) -> QLabel: ...


__all__ = ["CBIRTrainTabHostProtocol"]
