"""Worker teardown on cancel/close.

Extracted from ``entity_recon_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from gui.src.helpers.worker_teardown import stop_workers

from ._tab_bound import TabBoundController


class EntityReconLifecycleController(TabBoundController):
    """Interrupts/joins any active worker threads on cancel or window close."""

    def cancel_loading(self):
        stop_workers(*list(getattr(self, "_threads", [])))
        self._threads.clear()

    def closeEvent(self, event):
        self.cancel_loading()


_LifecycleMixin = EntityReconLifecycleController  # COMPAT(ui-arch-23): remove after callers drop the mixin name

__all__ = ["EntityReconLifecycleController", "_LifecycleMixin"]
