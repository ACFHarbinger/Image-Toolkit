"""App-level zoom (§UI.Zoom): Ctrl+Wheel and the underlying font-scale offset.

Extracted from ``main_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent


class _ZoomMixin:
    """Ctrl+Wheel-driven global zoom in/out, layered on top of font_scale."""

    def zoom_in(self) -> None:
        """Increase the global app zoom by 10% (max +100%) and reapply theme."""
        if not hasattr(self, "cached_creds") or not self.cached_creds:
            return
        prefs = self.cached_creds.setdefault("preferences", {})
        current = prefs.get("app_zoom", 0)
        if current >= 100:  # cap at +100% on top of font_scale
            return
        prefs["app_zoom"] = current + 10
        self.set_application_theme(self.current_theme)

    def zoom_out(self) -> None:
        """Decrease the global app zoom by 10% (min −50%) and reapply theme."""
        if not hasattr(self, "cached_creds") or not self.cached_creds:
            return
        prefs = self.cached_creds.setdefault("preferences", {})
        current = prefs.get("app_zoom", 0)
        if current <= -50:  # floor at −50%
            return
        prefs["app_zoom"] = current - 10
        self.set_application_theme(self.current_theme)

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        """Ctrl + Wheel Up/Down → zoom in / zoom out globally."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)


__all__ = ["_ZoomMixin"]
