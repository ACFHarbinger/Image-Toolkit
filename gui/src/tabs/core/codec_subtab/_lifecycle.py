"""Worker teardown overrides for CodecSubTab.

Extracted from ``codec_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import contextlib


class _LifecycleMixin:
    """Cancels the codec-scan/conversion workers and closes preview windows."""

    def cancel_loading(self):
        super().cancel_loading()

        if hasattr(self, "dual"):
            self.dual.cancel_loading()

        if self._codec_scan_worker:
            with contextlib.suppress(Exception):
                self._codec_scan_worker.stop()
            self._codec_scan_worker = None

        if self.worker:
            try:
                if hasattr(self.worker, "stop"):
                    self.worker.stop()
                elif hasattr(self.worker, "cancel"):
                    self.worker.cancel()
            except Exception:
                pass

        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()

    def closeEvent(self, event):
        self.cancel_conversion()
        self.cancel_loading()
        super().closeEvent(event)


__all__ = ["_LifecycleMixin"]
