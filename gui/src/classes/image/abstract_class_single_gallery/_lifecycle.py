"""Worker/timer teardown and gallery widget clearing.

Extracted from ``abstract_class_single_gallery.py`` -- pure code motion, no
logic change. ``cancel_loading``/``clear_gallery_widgets`` guard the
deleteOrphaned use-after-free crash class documented in
``.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`` -- moved
verbatim, comments included, and diffed against the pre-split original to
confirm zero logic drift.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, List

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication
from gui.src.constants.classes import ABSTRACT_CLASS_SINGLE_GALLERY__WORKER_DRAIN_TIMEOUT_MS

if TYPE_CHECKING:
    from ..protos.abstract_class_single_gallery import AbstractClassSingleGalleryHostProtocol

# How long cancel_loading() will block waiting for already-dispatched pool
# workers to actually finish before tearing down gallery widgets. Any FIXED
# bound here is unsafe: VideoLoaderWorker's fallback chain (ffmpegthumbnailer,
# then ffmpeg seeking to 5s, then ffmpeg seeking to 0s -- video_thumbnailer.py)
# can stack up to three independent 15s subprocess timeouts (~45s worst case)
# on a single corrupt/hanging video file. A 500ms bound was tried first and
# proved insufficient in practice (hs_err_pid116664.log: the exact same
# use-after-free race this wait exists to close, just needing a slower worker
# to hit the now-wider window) -- picking a *longer* fixed bound would only
# repeat that mistake with smaller odds, not eliminate it. -1 (Qt's own
# sentinel) waits until the pool is actually idle, which is the only way to
# guarantee no worker is still running when the caller proceeds to tear down
# gallery widgets. Workers are still asked to cooperatively cancel first
# (`.stop()`), so this is expected to return quickly in the overwhelming
# majority of cases; the tradeoff is a rare, bounded-by-subprocess-timeout UI
# pause instead of a crash.


class _LifecycleMixin:
    """Cancels in-flight loads and tears down gallery widgets safely."""

    def closeEvent(self: "AbstractClassSingleGalleryHostProtocol", event):
        """Cleanup processes on close."""
        self.cancel_loading()
        super().closeEvent(event)  # type: ignore[misc,safe-super]

    def cancel_loading(self: "AbstractClassSingleGalleryHostProtocol"):
        """Stops all active timers and background workers."""
        # Invalidate any queued (not yet dispatched) load chunks
        self._load_generation += 1
        if self._populate_timer.isActive():
            self._populate_timer.stop()
        if self._resize_timer.isActive():
            self._resize_timer.stop()
        if (
            hasattr(self, "search_debounce_timer")
            and self.search_debounce_timer.isActive()
        ):
            self.search_debounce_timer.stop()

        # Stop all active workers
        had_pending_workers = bool(self._active_workers)
        for worker in list(self._active_workers):
            with contextlib.suppress(Exception):
                worker.stop()
        self._active_workers.clear()

        if hasattr(self, "thread_pool"):
            self.thread_pool.clear()
            # `.stop()`/`.clear()` above are best-effort: a worker already
            # dispatched to a pool thread ignores both and keeps running.
            # Callers of cancel_loading() (clear_gallery_widgets(), directory
            # switches) proceed to deleteLater() the gallery's thumbnail
            # widgets immediately afterward; without this wait, a still-running
            # worker's queued cross-thread signal can be delivered concurrently
            # with that teardown and crash inside Qt's own connection
            # bookkeeping (QObjectPrivate::ConnectionData::deleteOrphaned,
            # observed via hs_err_pid79171.log switching from an image to a
            # video directory scan). Matches the same wait already used in
            # AbstractClassTwoGalleries.closeEvent() for the tab-close path.
            #
            # #444: guard the drain against the second cancel_loading() of a
            # single refresh cycle (refresh_gallery_view() calls it, then
            # clear_gallery_widgets() calls it again). The first call already
            # drained the pool and flushed deferred deletions, and nothing is
            # dispatched between the two, so the unbounded wait and the
            # app-wide flush are pure overhead there. Any worker still alive
            # (tracked at entry, or reported by the pool) still takes the
            # full drain path.
            if had_pending_workers or self.thread_pool.activeThreadCount() > 0:
                self.thread_pool.waitForDone(ABSTRACT_CLASS_SINGLE_GALLERY__WORKER_DRAIN_TIMEOUT_MS)
                # waitForDone() blocks THIS thread until pool workers finish; it
                # does not pump this thread's own event loop meanwhile. Any
                # deleteLater() calls already queued from an earlier, rapid
                # directory switch are still unprocessed at this point -- flush
                # them before the caller proceeds to tear down/rebuild widgets
                # again (see .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md
                # Addendum 8). Deliberately narrowed to DeferredDelete events only
                # (not a full processEvents()): a full processEvents() also
                # delivers ordinary queued cross-thread signals (e.g. a stale
                # scanner's scan_finished), reentrantly running application code
                # mid-teardown -- the actual cause of the round-9 recurrence, see
                # Addendum 9.
                QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        # CRITICAL FIX: Clear loading paths so interrupted loads don't block future attempts
        self._loading_paths.clear()
        if hasattr(self, "found_loading_paths"):
            self.found_loading_paths.clear()

    def clear_gallery_widgets(self: "AbstractClassSingleGalleryHostProtocol"):
        # Clear path_to_card_widget BEFORE cancel_loading()'s DeferredDelete
        # flush, not after. cancel_loading() flushes deleteLater() calls
        # queued by an earlier, rapid directory switch -- widgets that switch
        # actually destroys in C++ right here, during the flush. Any
        # reentrant signal handler that reads path_to_card_widget during that
        # same flush (e.g. update_preview_highlight(), a @Slot reachable via
        # a queued connection) would otherwise see a *not-yet-cleared* dict
        # still pointing at those same widgets mid-destruction -- a
        # dangling-reference race that crashes with a real SIGSEGV inside Qt
        # (e.g. QObject::property()) rather than the RuntimeError Qt raises
        # for the ordinary already-destroyed case, since the object's memory
        # can already be freed/reused by the time the stale lookup runs.
        # Clearing first means any such reentrant lookup sees an empty dict
        # and safely no-ops instead.
        self.path_to_card_widget.clear()
        self.cancel_loading()
        self._paginated_paths: List[str] = []

        if not self.gallery_layout:
            return
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()


__all__ = ["_LifecycleMixin", "ABSTRACT_CLASS_SINGLE_GALLERY__WORKER_DRAIN_TIMEOUT_MS"]
