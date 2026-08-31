"""Lifecycle helpers for Wallpaper's incremental directory scanner."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ....protos.wallpaper_common_base import WallpaperCommonBaseHostProtocol


class _ScannerLifecycleMixin:
    """Cancel scans without constructing or destroying Qt worker threads."""

    def _stop_legacy_thread(self, thread: Any) -> None:
        """Drain a scanner retained by an instance created before hot reload."""
        if thread is None:
            return
        with contextlib.suppress(RuntimeError):
            if thread.isRunning():
                request = getattr(thread, "requestInterruption", None)
                if callable(request):
                    request()
                stop = getattr(thread, "stop", None)
                if callable(stop):
                    stop()
                thread.quit()
                thread.wait()
        with contextlib.suppress(RuntimeError):
            thread.deleteLater()

    def _stop_legacy_scanner_threads(
        self: "WallpaperCommonBaseHostProtocol",
    ) -> None:
        self._stop_legacy_thread(getattr(self, "img_scanner_thread", None))
        self._stop_legacy_thread(getattr(self, "vid_scanner_thread", None))
        self.img_scanner_worker = None
        self.img_scanner_thread = None
        self.vid_scanner_worker = None
        self.vid_scanner_thread = None

    def _stop_scanner_threads(self: "WallpaperCommonBaseHostProtocol") -> None:
        self._cancel_directory_scan()
        self._stop_legacy_scanner_threads()
        self._scan_pipeline_busy = False

    def _stop_vid_scanner_worker(self: "WallpaperCommonBaseHostProtocol") -> None:
        self._stop_legacy_thread(getattr(self, "vid_scanner_thread", None))
        self.vid_scanner_worker = None
        self.vid_scanner_thread = None


__all__ = ["_ScannerLifecycleMixin"]
