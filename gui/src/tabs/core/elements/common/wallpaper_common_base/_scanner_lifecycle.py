"""Scanner-thread stop/drain helpers -- crash-history-sensitive, DO NOT alter logic.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring). These two methods
guard against the deleteOrphaned use-after-free crash class documented in
``.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`` -- every
comment below is load-bearing context for a real, previously-observed
crash, not incidental documentation.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication


class _ScannerLifecycleMixin:
    """Stop and fully drain the image/video scanner QThreads before any teardown."""

    def _stop_vid_scanner_worker(self) -> None:
        """Stop, drain, and clear self.vid_scanner_worker if one exists.

        Extracted so _on_image_scan_finished() can call it too, right
        before starting a fresh VideoScannerWorker -- otherwise a second
        image scan finishing while an earlier video scan is still running
        would overwrite self.vid_scanner_worker with the new instance
        while the old one keeps running, unstopped and unwaited-for, still
        connected to _add_video_thumbnail_manual (see Addendum 9 in
        .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md).
        """
        if self.vid_scanner_worker is not None:
            _tag = f"[thread-lifecycle] panel={id(self):x} vid_worker={id(self.vid_scanner_worker):x} tid={threading.get_ident()}"
            try:
                if self.vid_scanner_worker.isRunning():
                    print(f"{_tag} requestInterruption+stop+quit", flush=True)
                    self.vid_scanner_worker.requestInterruption()
                    self.vid_scanner_worker.stop()
                    self.vid_scanner_worker.quit()
                    print(f"{_tag} wait() starting", flush=True)
                    self.vid_scanner_worker.wait()  # unbounded
                    print(f"{_tag} wait() returned", flush=True)
                print(f"{_tag} deleteLater()", flush=True)
                self.vid_scanner_worker.deleteLater()
            except RuntimeError:
                pass
            self.vid_scanner_worker = None

    def _stop_scanner_threads(self) -> None:
        """Stop and fully drain this instance's scanner threads.

        These are bespoke QThread subclasses (ImageScannerWorker/
        VideoScannerWorker), not QRunnable tasks tracked by
        cancel_loading()'s thread_pool -- that fix (issue #81) does not
        cover them. Must be called, on every affected instance, BEFORE any
        widget teardown or shared-cache mutation: an old scanner thread left
        running is free to deliver a queued thumbnail_ready signal
        referencing widgets that are mid-deletion or already replaced --
        the same use-after-free crash class documented in
        .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md. Waits are
        deliberately unbounded: VideoScannerWorker's internal
        ThreadPoolExecutor can't be force-killed mid-subprocess and its
        context-manager __exit__ already blocks until truly idle regardless
        of any earlier non-blocking shutdown() call, so any fixed timeout
        can return while it's still running.
        """
        if self.img_scanner_thread is not None:
            _tag = f"[thread-lifecycle] panel={id(self):x} img_thread={id(self.img_scanner_thread):x} tid={threading.get_ident()}"
            if self.img_scanner_thread.isRunning():
                print(f"{_tag} requestInterruption+quit", flush=True)
                self.img_scanner_thread.requestInterruption()
                self.img_scanner_thread.quit()
                print(f"{_tag} wait() starting", flush=True)
                self.img_scanner_thread.wait()  # unbounded
                print(f"{_tag} wait() returned", flush=True)
            print(f"{_tag} deleteLater()", flush=True)
            self.img_scanner_thread.deleteLater()
            self.img_scanner_thread = None

        self._stop_vid_scanner_worker()

        # QThread.wait() above blocks THIS (calling/main) thread until the
        # OTHER thread finishes -- it does not pump this thread's own event
        # loop while waiting. Any deleteLater() calls already queued from an
        # earlier, rapid directory switch (this method's own two calls just
        # above, on a PREVIOUS invocation, plus clear_gallery_widgets()'s
        # widget teardown loop) are therefore still sitting unprocessed in
        # the event queue at this point, no matter how long the wait above
        # took. If the caller proceeds straight to tearing down/rebuilding
        # widgets again without this queue ever being flushed, repeated
        # rapid switches (e.g. restore -> browse video -> browse image ->
        # browse video again, each "immediately") can pile up multiple
        # generations of pending deferred-deletion events before any of
        # them run, risking the same use-after-free crash class this whole
        # file is already guarding against, just via queue backlog instead
        # of a still-running thread. Flush it explicitly before returning.
        # Deliberately narrowed to DeferredDelete events only (not a full
        # processEvents()): a full processEvents() also delivers ordinary
        # queued cross-thread signals -- e.g. a stale scanner's
        # scan_finished, reentrantly running _on_image_scan_finished() (and
        # thus starting a brand-new VideoScannerWorker) from inside THIS
        # method, before the caller has even updated self.scanned_dir to
        # the new directory. That reentrancy was the actual mechanism
        # behind the deleteOrphaned crash recurring after the round-9 fix
        # (see Addendum 9 in
        # .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md).
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


__all__ = ["_ScannerLifecycleMixin"]
