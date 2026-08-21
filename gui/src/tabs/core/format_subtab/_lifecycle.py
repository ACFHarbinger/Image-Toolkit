"""Worker/window teardown overrides for FormatSubTab.

Extracted from ``format_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import contextlib


class _LifecycleMixin:
    """Cancels the conversion worker and closes open preview windows."""

    def cancel_loading(self):
        """Stops all active timers and background workers."""
        super().cancel_loading()

        if self.worker:
            try:
                # Use stop() which we just added as an alias for cancel()
                if hasattr(self.worker, "stop"):
                    self.worker.stop()
                elif hasattr(self.worker, "cancel"):
                    self.worker.cancel()
            except Exception:
                pass

        # Close sub-windows
        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()

    def closeEvent(self, event):
        """Cleanup processes on close."""
        self.cancel_conversion()
        self.cancel_loading()
        super().closeEvent(event)


__all__ = ["_LifecycleMixin"]
