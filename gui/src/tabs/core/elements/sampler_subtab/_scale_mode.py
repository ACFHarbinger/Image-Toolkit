"""Scale-mode radio toggle (factor vs. target dimensions).

Extracted from ``sampler_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Slot


class _ScaleModeMixin:
    """Toggles visibility between the scale-factor and target-dimension widgets."""

    @Slot(bool)
    def _on_scale_mode_changed(self, factor_selected: bool):
        self._factor_widget.setVisible(factor_selected)
        self._dims_widget.setVisible(not factor_selected)


__all__ = ["_ScaleModeMixin"]
