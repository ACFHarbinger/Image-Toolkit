"""Loss-function combo toggle: enables temperature xor margin field.

Extracted from ``cbir_train_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Slot

from ._tab_bound import TabBoundController


class CBIRTrainLossToggleController(TabBoundController):
    """Enables the temperature field for InfoNCE, margin field for Triplet."""

    @Slot(int)
    def _on_loss_changed(self, idx: int) -> None:
        loss_id = self._loss_fn.currentData()
        self._temperature.setEnabled(loss_id == "infonce")
        self._margin.setEnabled(loss_id == "triplet")


# COMPAT(ui-arch-23): legacy mixin alias
_LossToggleMixin = CBIRTrainLossToggleController

__all__ = ["CBIRTrainLossToggleController", "_LossToggleMixin"]
