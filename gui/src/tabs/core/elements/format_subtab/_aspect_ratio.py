"""Aspect-ratio controls toggling and preset-to-custom-W/H sync.

Extracted from ``format_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Slot


class _AspectRatioMixin:
    """Enable/disable the AR controls and keep preset ↔ custom W/H in sync."""

    @Slot(bool)
    def toggle_ar_controls(self, checked: bool):
        self.ar_controls_widget.setEnabled(checked)

    @Slot(str)
    def on_ar_combo_change(self, text):
        if text == "Custom":
            self.ar_custom_container.setVisible(True)
        else:
            self.ar_custom_container.setVisible(False)
            try:
                if ":" in text:
                    w, h = map(int, text.split(":"))
                    self.ar_w.setValue(w)
                    self.ar_h.setValue(h)
            except Exception as e:
                print(f"Error checking directory: {e}")
                return


__all__ = ["_AspectRatioMixin"]
