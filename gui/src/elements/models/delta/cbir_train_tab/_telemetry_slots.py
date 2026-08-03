"""Main-thread slots reacting to training/index-build background signals.

Extracted from ``cbir_train_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox, QWidget

if TYPE_CHECKING:
    from ...protos.cbir_train_tab import CBIRTrainTabHostProtocol

try:
    from backend.src.models.tuning.cbir_tuner import CBIRTuner

    _TRAINER_OK = True
except ImportError:
    _TRAINER_OK = False
    CBIRTuner = None  # type: ignore[assignment,misc]


class _TelemetrySlotsMixin:
    """Handles sig_log/sig_metrics/sig_epoch/sig_done/sig_index_* signals."""

    @Slot(str)
    def _on_log(self: "CBIRTrainTabHostProtocol", msg: str) -> None:
        self._log_box.append(msg)
        sb = self._log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    @Slot(dict)
    def _on_metrics(self: "CBIRTrainTabHostProtocol", m: dict) -> None:
        if "total" in m:
            self._loss_chart.push(float(m["total"]))

    @Slot(int, dict)
    def _on_epoch(self: "CBIRTrainTabHostProtocol", epoch: int, m: dict) -> None:
        self._epoch_progress.setMaximum(self._epochs.value())
        self._epoch_progress.setValue(epoch)

        r1 = m.get("recall_at_1", 0.0)
        r5 = m.get("recall_at_5", 0.0)
        r10 = m.get("recall_at_10", 0.0)
        loss = m.get("total", 0.0)

        self._recall_label.setText(
            f"Recall@1: {r1:.3f}   Recall@5: {r5:.3f}   Recall@10: {r10:.3f}"
        )
        self._lbl_epoch_loss.setText(f"<b>Last loss</b><br/>{loss:.4f}")

        # Update best R@1 label
        current_best = getattr(self, "_best_r1", 0.0)
        if r1 > current_best:
            self._best_r1 = r1
            self._lbl_best_r1.setText(f"<b>Best R@1</b><br/>{r1:.3f}")

    @Slot(str, str)
    def _on_done(self: "CBIRTrainTabHostProtocol", status: str, msg: str) -> None:
        self._btn_start.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        if _TRAINER_OK and CBIRTuner is not None:
            CBIRTuner.is_cancelled = False
        if status == "ok":
            QMessageBox.information(cast(QWidget, self), "Training complete", msg)
        elif status == "cancel":
            QMessageBox.warning(cast(QWidget, self), "Cancelled", msg)
        else:
            QMessageBox.critical(cast(QWidget, self), "Training error", msg)

    @Slot(int, int)
    def _on_index_progress(self: "CBIRTrainTabHostProtocol", done: int, total: int) -> None:
        self._index_progress.setValue(int(done / max(total, 1) * 100))

    @Slot(str, str)
    def _on_index_done(self: "CBIRTrainTabHostProtocol", status: str, msg: str) -> None:
        self._btn_build_index.setEnabled(True)
        self._index_progress.setVisible(False)
        if status == "ok":
            QMessageBox.information(cast(QWidget, self), "Index built", msg)
        else:
            QMessageBox.critical(cast(QWidget, self), "Index build failed", msg)


__all__ = ["_TelemetrySlotsMixin"]
