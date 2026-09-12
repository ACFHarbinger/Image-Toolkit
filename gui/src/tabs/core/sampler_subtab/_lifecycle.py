"""Worker teardown overrides for SamplerSubTab.

Extracted from ``sampler_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from gui.src.helpers.worker_teardown import stop_worker


class _LifecycleMixin:
    """Cancels the resample worker on teardown/close."""

    def cancel_loading(self):
        super().cancel_loading()
        if hasattr(self, "dual"):
            self.dual.cancel_loading()
        # No join here (as before): the pool thread + ffmpeg procs die off
        # on their own; closeEvent below joins for the teardown path.
        stop_worker(getattr(self, "worker", None), join=False)

    def closeEvent(self, event):
        stop_worker(getattr(self, "worker", None))
        self.cancel_loading()
        super().closeEvent(event)


__all__ = ["_LifecycleMixin"]
