"""Worker teardown overrides for ``SearchTab``.

Extracted from ``search_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import contextlib


class _LifecycleMixin:
    """Cancel the search worker and close open preview windows."""

    def cancel_loading(self):
        """Stops all active timers and background workers."""
        super().cancel_loading()

        if self.current_search_worker:
            self.current_search_worker.cancel()

        # Close sub-windows
        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()

    def closeEvent(self, event):
        """Cleanup processes on close."""
        self.cancel_loading()
        super().closeEvent(event)


__all__ = ["_LifecycleMixin"]
