"""Worker teardown on cancel/close.

Extracted from ``entity_recon_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import logging

from ._tab_bound import TabBoundController

logger = logging.getLogger(__name__)


class EntityReconLifecycleController(TabBoundController):
    """Interrupts/joins any active worker threads on cancel or window close."""

    def cancel_loading(self):
        for t in list(self._threads):
            try:
                t.requestInterruption()
                t.quit()
                t.wait()
            except Exception:  # noqa: BLE001
                logger.debug("Suppressed Exception in cancel_loading", exc_info=True)
        self._threads.clear()

    def closeEvent(self, event):
        self.cancel_loading()


_LifecycleMixin = EntityReconLifecycleController  # COMPAT(ui-arch-23): remove after callers drop the mixin name

__all__ = ["EntityReconLifecycleController", "_LifecycleMixin"]
