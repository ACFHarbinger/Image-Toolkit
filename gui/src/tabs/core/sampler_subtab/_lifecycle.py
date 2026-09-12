"""Worker teardown overrides for SamplerSubTab.

Extracted from ``sampler_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from gui.src.helpers.worker_teardown import stop_worker

from ._tab_bound import TabBoundController


class SamplerLifecycleController(TabBoundController):
    """Cancels the resample worker on teardown/close."""

    def cancel_loading(self):
        if hasattr(self.tab, "dual"):
            self.tab.dual.cancel_loading()
        stop_worker(getattr(self, "worker", None), join=False)

    def closeEvent(self, event):
        stop_worker(getattr(self, "worker", None))
        self.cancel_loading()


# COMPAT(ui-arch-23): legacy mixin alias
_LifecycleMixin = SamplerLifecycleController

__all__ = ["SamplerLifecycleController", "_LifecycleMixin"]
