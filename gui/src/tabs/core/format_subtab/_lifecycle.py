"""Worker/window teardown overrides for FormatSubTab.

Extracted from ``format_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from gui.src.helpers.worker_teardown import close_windows, stop_worker


class _LifecycleMixin:
    """Cancels the conversion worker and closes open preview windows."""

    def cancel_loading(self):
        """Stops all active timers and background workers."""
        super().cancel_loading()

        if hasattr(self, "dual"):
            self.dual.cancel_loading()

        # Fire-and-forget (as before): the finished slots tolerate teardown.
        stop_worker(getattr(self, "worker", None), join=False)

        # Close sub-windows
        close_windows(self, "open_preview_windows")

    def closeEvent(self, event):
        """Cleanup processes on close."""
        self.cancel_conversion()
        self.cancel_loading()
        super().closeEvent(event)


__all__ = ["_LifecycleMixin"]
