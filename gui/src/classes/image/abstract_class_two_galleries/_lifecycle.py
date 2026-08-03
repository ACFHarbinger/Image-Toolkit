"""Worker/timer teardown, close-event cleanup, and gallery reset -- crash-
history sensitive, DO NOT alter logic.

Extracted from ``abstract_class_two_galleries.py`` -- pure code motion, no
logic change (see ``_navigation.py``'s docstring). ``cancel_loading()``'s
unbounded ``thread_pool.waitForDone()`` + ``DeferredDelete`` flush guards
the deleteOrphaned use-after-free crash class documented in
``.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`` -- every
comment below is load-bearing context for a real, previously-observed
crash, not incidental documentation.
"""

from __future__ import annotations

import contextlib
import os

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QGridLayout

if TYPE_CHECKING:
    from ..protos.abstract_class_two_galleries import AbstractClassTwoGalleriesHostProtocol

# How long cancel_loading()/closeEvent() will block waiting for already-
# dispatched pool workers to actually finish before tearing down gallery
# widgets. Any FIXED bound here is unsafe: VideoLoaderWorker's fallback
# chain (ffmpegthumbnailer, then ffmpeg seeking to 5s, then ffmpeg seeking to
# 0s -- video_thumbnailer.py) can stack up to three independent 15s
# subprocess timeouts (~45s worst case) on a single corrupt/hanging video
# file. A 500ms bound was tried first and proved insufficient in practice
# (hs_err_pid116664.log: the exact same use-after-free race this wait exists
# to close, just needing a slower worker to hit the now-wider window) --
# picking a *longer* fixed bound would only repeat that mistake with smaller
# odds, not eliminate it. -1 (Qt's own sentinel) waits until the pool is
# actually idle, which is the only way to guarantee no worker is still
# running when the caller proceeds to tear down gallery widgets. Workers are
# still asked to cooperatively cancel first (`.stop()`), so this is expected
# to return quickly in the overwhelming majority of cases; the tradeoff is a
# rare, bounded-by-subprocess-timeout UI pause instead of a crash.
_WORKER_DRAIN_TIMEOUT_MS = -1


class _LifecycleMixin:
    """Cancel loading, close-event teardown, and clear/restore gallery state."""

    def cancel_loading(self: "AbstractClassTwoGalleriesHostProtocol"):
        """Stops all active timers and background workers."""
        # Invalidate any queued (not yet dispatched) load chunks
        self._load_generation += 1
        if self._populate_found_timer.isActive():
            self._populate_found_timer.stop()
        if self._resize_timer.isActive():
            self._resize_timer.stop()
        if hasattr(self, "found_search_timer") and self.found_search_timer.isActive():
            self.found_search_timer.stop()

        # Stop all active workers
        for worker in list(self._active_workers):
            with contextlib.suppress(Exception):
                worker.stop()
        self._active_workers.clear()

        if hasattr(self, "thread_pool"):
            self.thread_pool.clear()
            # `.stop()`/`.clear()` above are best-effort: a worker already
            # dispatched to a pool thread ignores both and keeps running.
            # Callers of cancel_loading() (clear_galleries(), directory/tab
            # switches) proceed to deleteLater() the gallery's thumbnail
            # widgets immediately afterward; without this wait, a still-running
            # worker's queued cross-thread signal can be delivered concurrently
            # with that teardown and crash inside Qt's own connection
            # bookkeeping (QObjectPrivate::ConnectionData::deleteOrphaned,
            # observed via hs_err_pid79171.log switching from an image to a
            # video directory scan). closeEvent() already did this same wait
            # for the tab-close path; this extends the same fix to every
            # other cancel_loading() caller.
            self.thread_pool.waitForDone(_WORKER_DRAIN_TIMEOUT_MS)
            # waitForDone() blocks THIS thread until pool workers finish; it
            # does not pump this thread's own event loop meanwhile. Any
            # deleteLater() calls already queued from an earlier, rapid
            # directory switch are still unprocessed at this point --
            # flush them before the caller proceeds to tear down/rebuild
            # widgets again, or repeated rapid switches can pile up
            # multiple generations of pending deferred-deletion events
            # (see .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md
            # Addendum 8). Narrowed to DeferredDelete only -- see Addendum 9:
            # a full processEvents() also delivers ordinary queued
            # cross-thread signals reentrantly, mid-teardown.
            QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def closeEvent(self: "AbstractClassTwoGalleriesHostProtocol", event):
        """Cleanup processes on close."""
        self.cancel_loading()
        # Clean up pool
        self.thread_pool.clear()
        # Ensure signals don't fire to a destroyed object
        self.thread_pool.waitForDone(_WORKER_DRAIN_TIMEOUT_MS)
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)  # flush pending deleteLater()s -- see cancel_loading()
        super().closeEvent(event)  # type: ignore[misc,safe-super]

    def clear_galleries(self: "AbstractClassTwoGalleriesHostProtocol", clear_data=True):
        if clear_data:
            self.found_files.clear()
            self.selected_files.clear()
            self.path_to_label_map.clear()
            self.found_current_page = 0
            self.selected_current_page = 0
            self._selected_pixmap_cache.clear()

        self.cancel_loading()
        self._clear_layout(self.found_gallery_layout)  # pyrefly: ignore [bad-argument-type]
        self.common_show_placeholder(
            self.found_gallery_layout, "No images found/loaded.", 1
        )
        self._update_pagination_ui(is_found=True)

        self._clear_layout(self.selected_gallery_layout)  # pyrefly: ignore [bad-argument-type]
        self.common_show_placeholder(
            self.selected_gallery_layout, "Selected files will appear here.", 1
        )
        self._update_pagination_ui(is_found=False)

        self.on_selection_changed()

    def _restore_selected_files(self: "AbstractClassTwoGalleriesHostProtocol", config: dict):
        """Restores the selected gallery from a saved config, skipping missing paths."""
        saved = config.get("selected_files", [])
        if not saved:
            return
        valid = [p for p in saved if os.path.isfile(p)]
        if valid:
            self.selected_files = valid
            self.refresh_selected_panel()
            self.on_selection_changed()

    def _clear_layout(self: "AbstractClassTwoGalleriesHostProtocol", layout: Optional[QGridLayout]):
        if not layout:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()


__all__ = ["_LifecycleMixin", "_WORKER_DRAIN_TIMEOUT_MS"]
