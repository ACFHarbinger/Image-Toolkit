"""Worker/window teardown overrides for CodecSubTab and FormatSubTab."""

from __future__ import annotations

import contextlib
import logging

logger = logging.getLogger(__name__)


class _LifecycleMixin:
    """Cancels scan/conversion workers and closes open preview windows."""

    def cancel_loading(self):
        super().cancel_loading()

        if hasattr(self, "dual"):
            self.dual.cancel_loading()

        scan_worker = getattr(self, "_codec_scan_worker", None)
        if scan_worker:
            with contextlib.suppress(Exception):
                scan_worker.stop()
            self._codec_scan_worker = None

        if self.worker:
            try:
                if hasattr(self.worker, "stop"):
                    self.worker.stop()
                elif hasattr(self.worker, "cancel"):
                    self.worker.cancel()
            except Exception:
                logger.debug(
                    "Suppressed Exception in _LifecycleMixin.cancel_loading",
                    exc_info=True,
                )

        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()

    def closeEvent(self, event):
        self.cancel_conversion()
        self.cancel_loading()
        super().closeEvent(event)


__all__ = ["_LifecycleMixin"]
