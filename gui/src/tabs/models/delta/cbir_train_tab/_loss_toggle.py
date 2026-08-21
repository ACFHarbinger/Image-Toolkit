"""Loss-function combo toggle: enables temperature xor margin field.

Extracted from ``cbir_train_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Slot

if TYPE_CHECKING:
    from ...protos.cbir_train_tab import CBIRTrainTabHostProtocol


class _LossToggleMixin:
    """Enables the temperature field for InfoNCE, margin field for Triplet."""

    @Slot(int)
    def _on_loss_changed(self: "CBIRTrainTabHostProtocol", idx: int) -> None:
        loss_id = self._loss_fn.currentData()
        self._temperature.setEnabled(loss_id == "infonce")
        self._margin.setEnabled(loss_id == "triplet")


__all__ = ["_LossToggleMixin"]
