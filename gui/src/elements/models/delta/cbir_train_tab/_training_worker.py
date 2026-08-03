"""CBIRTuner training-thread dispatch and cancellation.

Extracted from ``cbir_train_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional, cast

from PySide6.QtWidgets import QMessageBox, QWidget

if TYPE_CHECKING:
    from ...protos.cbir_train_tab import CBIRTrainTabHostProtocol

try:
    from backend.src.models.tuning.cbir_tuner import CBIRTuner

    _TRAINER_OK = True
except ImportError:
    _TRAINER_OK = False
    CBIRTuner = None  # type: ignore[assignment,misc]


class _TrainingWorkerMixin:
    """Starts/cancels the background CBIRTuner training thread."""

    _train_thread: Optional[threading.Thread]

    def _start_training(self: "CBIRTrainTabHostProtocol") -> None:
        if not _TRAINER_OK or CBIRTuner is None:
            QMessageBox.critical(
                cast(QWidget, self), "Missing dependencies",
                "Could not import CBIRTuner.\n"
                "Ensure PyTorch and transformers are installed.",
            )
            return

        img_dir = self._img_dir.text().strip()
        if not img_dir:
            QMessageBox.warning(cast(QWidget, self), "No directory", "Please select an image directory.")
            return

        self._btn_start.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._best_r1 = 0.0
        self._loss_chart.reset()
        self._log_box.clear()
        self._epoch_progress.setValue(0)
        self._epoch_progress.setMaximum(self._epochs.value())

        config = self.collect()

        tuner = CBIRTuner(
            config=config,
            on_log=lambda m: self.sig_log.emit(m),
            on_metrics=lambda m: self.sig_metrics.emit(m),
            on_epoch_end=lambda e, m: self.sig_epoch.emit(e, m),
        )

        def _run() -> None:
            try:
                tuner.train()
                # Auto-populate checkpoint path on success
                best = Path(config["output_dir"]) / "cbir_best.pt"
                if best.is_file():
                    self._ckpt_path.setText(str(best))
                self.sig_done.emit("ok", "Training finished successfully.")
            except Exception as exc:
                if _TRAINER_OK and CBIRTuner is not None and CBIRTuner.is_cancelled:
                    self.sig_done.emit("cancel", "Training cancelled by user.")
                else:
                    self.sig_done.emit("error", str(exc))

        train_thread = threading.Thread(target=_run, daemon=True)
        self._train_thread = train_thread
        train_thread.start()

    def _cancel_training(self: "CBIRTrainTabHostProtocol") -> None:
        if _TRAINER_OK and CBIRTuner is not None:
            CBIRTuner.cancel()
        self._btn_cancel.setEnabled(False)
        self._on_log("Cancellation requested…")


__all__ = ["_TrainingWorkerMixin"]
