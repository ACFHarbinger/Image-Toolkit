"""Worker teardown overrides for SamplerSubTab.

Extracted from ``sampler_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import contextlib


class _LifecycleMixin:
    """Cancels the resample worker on teardown/close."""

    def cancel_loading(self):
        super().cancel_loading()
        if self.worker:
            with contextlib.suppress(Exception):
                self.worker.cancel()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        self.cancel_loading()
        super().closeEvent(event)


__all__ = ["_LifecycleMixin"]
