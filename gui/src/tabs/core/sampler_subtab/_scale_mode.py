"""Scale-mode radio toggle (factor vs. target dimensions).

Extracted from ``sampler_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Slot

from ._tab_bound import TabBoundController


class SamplerScaleModeController(TabBoundController):
    """Toggles visibility between the scale-factor and target-dimension widgets."""

    @Slot(bool)
    def _on_scale_mode_changed(self, factor_selected: bool):
        self._factor_widget.setVisible(factor_selected)
        self._dims_widget.setVisible(not factor_selected)


# COMPAT(ui-arch-23): legacy mixin alias
_ScaleModeMixin = SamplerScaleModeController

__all__ = ["SamplerScaleModeController", "_ScaleModeMixin"]
