"""Worker teardown overrides for ``SimilarityTab``.

Extracted from ``similarity_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import contextlib

from gui.src.helpers.worker_teardown import close_windows, stop_workers


class _LifecycleMixin:
    """Cancel the similarity/deletion workers and close preview windows."""

    def cancel_loading(self):
        stop_workers(getattr(self, "_sim_worker", None), getattr(self, "worker", None))
        with contextlib.suppress(Exception):
            super().cancel_loading()
        if hasattr(self, "dual"):
            self.dual.cancel_loading()
        close_windows(self, "open_preview_windows")

    def closeEvent(self, event):
        self.cancel_loading()
        super().closeEvent(event)


__all__ = ["_LifecycleMixin"]
