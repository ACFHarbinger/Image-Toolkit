"""Worker/window teardown overrides for CodecSubTab and FormatSubTab."""

from __future__ import annotations

from gui.src.helpers.worker_teardown import close_windows, stop_workers


class _LifecycleMixin:
    """Cancels scan/conversion workers and closes open preview windows."""

    def cancel_loading(self):
        super().cancel_loading()

        if hasattr(self, "dual"):
            self.dual.cancel_loading()

        # Fire-and-forget (as before): pool/QThread workers die off on
        # their own; the finished slots already tolerate teardown.
        stop_workers(
            getattr(self, "_codec_scan_worker", None),
            getattr(self, "worker", None),
            join=False,
        )
        self._codec_scan_worker = None

        close_windows(self, "open_preview_windows")

    def closeEvent(self, event):
        self.cancel_conversion()
        self.cancel_loading()
        super().closeEvent(event)


__all__ = ["_LifecycleMixin"]
