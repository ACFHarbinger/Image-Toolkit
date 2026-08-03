"""Scanner-thread stop/drain helper -- crash-history-sensitive, DO NOT alter logic.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring). Guards against the
deleteOrphaned use-after-free crash class documented in
``.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`` -- every
comment below is load-bearing context for a real, previously-observed
crash, not incidental documentation.

Video-directory scanning (VideoScannerWorker) was reintroduced (Addendum
24) as a scan-only QThread -- no thumbnail generation inside it, unlike
the original that fanned decode work out across an internal
ThreadPoolExecutor -- run strictly AFTER the image scan settles (see
_scan_pipeline.py's _on_image_scan_finished), never concurrently with it.
_stop_vid_scanner_worker() below mirrors _stop_scanner_threads()'s
image-scanner handling exactly, including the Addendum 22
disconnect-before-teardown mitigation.
"""

from __future__ import annotations

import contextlib
import threading

from backend.src.core import telemetry
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication


class _ScannerLifecycleMixin:
    """Stop and fully drain the image scanner QThread before any teardown."""

    def _stop_scanner_threads(self) -> None:
        """Stop and fully drain this instance's image scanner thread.

        This is a bespoke QThread subclass (ImageScannerWorker), not a
        QRunnable task tracked by cancel_loading()'s thread_pool -- that
        fix (issue #81) does not cover it. Must be called, on every
        affected instance, BEFORE any widget teardown or shared-cache
        mutation: an old scanner thread left running is free to deliver a
        queued signal referencing widgets that are mid-deletion or
        already replaced -- the same use-after-free crash class
        documented in .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md.
        The wait is deliberately unbounded.
        """
        if self.img_scanner_thread is not None:
            _tag = f"[thread-lifecycle] panel={id(self):x} img_thread={id(self.img_scanner_thread):x} tid={threading.get_ident()}"
            _panel, _thread_id, _tid = id(self), id(self.img_scanner_thread), threading.get_ident()
            # Addendum 22: empty this worker's connection list up front,
            # before any stop/wait/teardown, so a later concurrent
            # deleteOrphaned() elsewhere has nothing left to race against
            # for THIS worker. Kept even after the video-scanning removal
            # (Addendum 23) -- this specific mitigation was never shown to
            # be harmful, only insufficient on its own for the video path.
            for _sig_name in ("scan_finished", "scan_error", "finished"):
                with contextlib.suppress(RuntimeError, TypeError):
                    getattr(self.img_scanner_thread, _sig_name).disconnect() # already disconnected, or the C++ object is gone
            telemetry.emit("thread-lifecycle", "img_thread.signals_disconnected", panel=_panel, img_thread=_thread_id, tid=_tid)
            if self.img_scanner_thread.isRunning():
                print(f"{_tag} requestInterruption+quit", flush=True)
                telemetry.emit("thread-lifecycle", "img_thread.stop_requested", panel=_panel, img_thread=_thread_id, tid=_tid)
                self.img_scanner_thread.requestInterruption()
                self.img_scanner_thread.quit()
                print(f"{_tag} wait() starting", flush=True)
                telemetry.emit("thread-lifecycle", "img_thread.wait.start", panel=_panel, img_thread=_thread_id, tid=_tid)
                self.img_scanner_thread.wait()  # unbounded
                print(f"{_tag} wait() returned", flush=True)
                telemetry.emit("thread-lifecycle", "img_thread.wait.end", panel=_panel, img_thread=_thread_id, tid=_tid)
            print(f"{_tag} deleteLater()", flush=True)
            telemetry.emit("thread-lifecycle", "img_thread.delete_later", panel=_panel, img_thread=_thread_id, tid=_tid)
            self.img_scanner_thread.deleteLater()
            self.img_scanner_thread = None

        # QThread.wait() above blocks THIS (calling/main) thread until the
        # OTHER thread finishes -- it does not pump this thread's own event
        # loop while waiting. Any deleteLater() calls already queued from an
        # earlier, rapid directory switch (this method's own call just
        # above, on a PREVIOUS invocation, plus clear_gallery_widgets()'s
        # widget teardown loop) are therefore still sitting unprocessed in
        # the event queue at this point, no matter how long the wait above
        # took. If the caller proceeds straight to tearing down/rebuilding
        # widgets again without this queue ever being flushed, repeated
        # rapid switches can pile up multiple generations of pending
        # deferred-deletion events before any of them run, risking the
        # same use-after-free crash class this whole file is already
        # guarding against, just via queue backlog instead of a
        # still-running thread. Flush it explicitly before returning.
        # Deliberately narrowed to DeferredDelete events only (not a full
        # processEvents()): a full processEvents() also delivers ordinary
        # queued cross-thread signals reentrantly, mid-teardown (see
        # Addendum 9 in .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md).
        telemetry.emit("thread-lifecycle", "sendPostedEvents.DeferredDelete", panel=id(self), tid=threading.get_ident())
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        # Also drain the video scanner thread, if any -- every caller of
        # _stop_scanner_threads() (this instance's own teardown AND the
        # peer loop in populate_scan_image_gallery()) needs both worker
        # types stopped before touching widgets.
        self._stop_vid_scanner_worker()

    def _stop_vid_scanner_worker(self) -> None:
        """Stop and fully drain this instance's video scanner thread.

        Mirrors _stop_scanner_threads() above exactly -- see its
        docstring for the full rationale. Kept as a distinct method (not
        folded into _stop_scanner_threads()) so callers that only care
        about one worker type don't have to pay for stopping both.
        """
        if getattr(self, "vid_scanner_thread", None) is None:
            return
        _panel, _thread_id, _tid = id(self), id(self.vid_scanner_thread), threading.get_ident()
        for _sig_name in ("scan_finished", "scan_error", "finished"):
            with contextlib.suppress(RuntimeError, TypeError):
                getattr(self.vid_scanner_thread, _sig_name).disconnect()
        telemetry.emit("thread-lifecycle", "vid_thread.signals_disconnected", panel=_panel, vid_thread=_thread_id, tid=_tid)
        if self.vid_scanner_thread.isRunning():
            telemetry.emit("thread-lifecycle", "vid_thread.stop_requested", panel=_panel, vid_thread=_thread_id, tid=_tid)
            self.vid_scanner_thread.requestInterruption()
            self.vid_scanner_thread.quit()
            telemetry.emit("thread-lifecycle", "vid_thread.wait.start", panel=_panel, vid_thread=_thread_id, tid=_tid)
            self.vid_scanner_thread.wait()  # unbounded
            telemetry.emit("thread-lifecycle", "vid_thread.wait.end", panel=_panel, vid_thread=_thread_id, tid=_tid)
        self.vid_scanner_thread.deleteLater()
        self.vid_scanner_thread = None

        telemetry.emit("thread-lifecycle", "vid_sendPostedEvents.DeferredDelete", panel=id(self), tid=threading.get_ident())
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


__all__ = ["_ScannerLifecycleMixin"]
