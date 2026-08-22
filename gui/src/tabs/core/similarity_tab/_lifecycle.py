"""Worker teardown overrides for ``SimilarityTab``.

Extracted from ``similarity_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import contextlib


class _LifecycleMixin:
    """Cancel the similarity/deletion workers and close preview windows."""

    def cancel_loading(self):
        worker = getattr(self, "_sim_worker", None)
        if worker and worker.isRunning():
            worker.requestInterruption()
            worker.wait()
        if self.worker and hasattr(self.worker, "isRunning") and self.worker.isRunning():
            with contextlib.suppress(Exception):
                if hasattr(self.worker, "stop"):
                    self.worker.stop()
                elif hasattr(self.worker, "cancel"):
                    self.worker.cancel()
                self.worker.requestInterruption()
                self.worker.wait()
        with contextlib.suppress(Exception):
            super().cancel_loading()
        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()

    def closeEvent(self, event):
        self.cancel_loading()
        super().closeEvent(event)


__all__ = ["_LifecycleMixin"]
