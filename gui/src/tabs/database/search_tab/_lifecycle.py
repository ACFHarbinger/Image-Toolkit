"""Worker teardown overrides for ``SearchTab``.

Extracted from ``search_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from gui.src.helpers.worker_teardown import close_windows, stop_worker


class _LifecycleMixin:
    """Cancel the search worker and close open preview windows."""

    def cancel_loading(self):
        """Stops all active timers and background workers."""
        super().cancel_loading()

        if hasattr(self, "dual"):
            self.dual.cancel_loading()

        # Fire-and-forget (as before): search runnables die off on their own.
        stop_worker(getattr(self, "current_search_worker", None), join=False)

        # Close sub-windows
        close_windows(self, "open_preview_windows")

    def closeEvent(self, event):
        """Cleanup processes on close."""
        self.cancel_loading()
        super().closeEvent(event)


__all__ = ["_LifecycleMixin"]
