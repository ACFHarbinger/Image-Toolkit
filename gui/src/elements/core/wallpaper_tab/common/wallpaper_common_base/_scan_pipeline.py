"""Directory-scan pipeline (image scan only) -- crash-history sensitive,
DO NOT alter logic.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring, and
``_scanner_lifecycle.py``'s for the crash class this whole pipeline's
staleness/serialization guards defend against). Every comment below is
load-bearing context for a real, previously-observed crash, not
incidental documentation.

Video-directory scanning (VideoScannerWorker) was reintroduced (Addendum
24, .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md) after 22
rounds targeting the deleteOrphaned/QObjectPrivate::connect() crash class
failed to close it via the original combined scan+thumbnail-generation
QThread (Addenda 21/22 made it *more* reliable rather than closing it).
The new VideoScannerWorker only lists file paths -- no internal
ThreadPoolExecutor, no thumbnail generation -- and runs strictly AFTER
the image scan settles (_on_image_scan_finished kicks it off instead of
calling _settle_scan_pipeline() directly), never concurrently with it, so
the busy-flag serialization and peer-reentrancy guards below cover both
scan phases as a single unit. Thumbnail generation for found video paths
goes through the same QThreadPool/QRunnable pipeline
(VideoLoaderWorker/BatchVideoLoaderWorker) as image thumbnails --
inherited from AbstractClassSingleGallery, never implicated in this crash
class.
"""

from __future__ import annotations

import os
import threading

from backend.src.constants import SUPPORTED_IMG_FORMATS
from backend.src.core import telemetry
from gui.src.helpers import ImageScannerWorker, VideoScannerWorker
from PySide6.QtCore import QTimer

from ......utils.sort_utils import natural_sort_key
from ......utils.guard.startup_probe_guard import startup_settle_remaining_ms


class _ScanPipelineMixin:
    """Serialized directory-switch scan pipeline: image scan, then video scan."""

    def populate_scan_image_gallery(self, directory: str, emit_signal: bool = True):
        if getattr(self, "background_type", None) == "Solid Color":
            return

        # Serialize overlapping switches (issue #81): every fix so far in
        # this file makes an *individual* overlapping switch safe by
        # rejecting stale deliveries after the fact, but still lets two
        # switches' teardown/create cycles run concurrently in the first
        # place. Rapid, back-to-back calls (the exact repro this whole
        # investigation is built around) still produce a tight burst of
        # QObject construction/destruction, and every crash observed keeps
        # landing inside PySide6/Shiboken's own binding-layer bookkeeping,
        # not application logic -- consistent with that subsystem having
        # limited headroom under heavy concurrent churn regardless of how
        # correct the staleness guards are. Not starting a second switch's
        # teardown until the first one's full scan pipeline (image scan)
        # has actually finished closes the overlap at its source instead
        # of only making each overlap individually safe. Only the *latest*
        # pending request is kept -- intermediate directories a user
        # rapidly clicked past are never actually worth rendering. A
        # watchdog timer force-clears the busy flag as a safety net in
        # case some exit path from the scan pipeline doesn't go through
        # _on_image_scan_finished()/handle_scan_error() (both of which
        # clear it normally) -- a stuck flag must never permanently block
        # all future switches.
        if getattr(self, "_scan_pipeline_busy", False):
            self._pending_scan_request = (directory, emit_signal)
            return

        if emit_signal:
            import traceback
            _stack = traceback.format_stack(limit=8)
            print(
                f"[thread-lifecycle] CALLER TRACE for populate_scan_image_gallery({directory!r}, emit_signal=True):\n"
                + "".join(_stack),
                flush=True,
            )
            telemetry.emit(
                "thread-lifecycle", "populate_scan_image_gallery.caller_trace",
                panel=id(self), directory=directory, stack="".join(_stack),
            )

        # Refuse to start a scanner QThread while Qt Multimedia's startup
        # device probe may still be in flight (issue #81 root cause #8):
        # racing it corrupts the heap. This floor is measured from the
        # probe's actual start time (see startup_probe_guard.py), not from
        # how long login/MainWindow construction happened to take, so it
        # protects a fast-login-then-immediate-browse sequence the same
        # way it protects the auto-restore path -- whichever call reaches
        # here first, during the settle window, simply reschedules itself.
        # Deliberately checked BEFORE the busy flag below is set: this is a
        # self-reschedule (not a second, distinct switch request), so it
        # must not trip the "already busy" path on its own retry.
        _remaining_ms = startup_settle_remaining_ms()
        print(
            f"[thread-lifecycle] panel={id(self):x} tid={threading.get_ident()} "
            f"populate_scan_image_gallery({directory!r}) emit_signal={emit_signal} "
            f"remaining_ms={_remaining_ms}",
            flush=True,
        )
        telemetry.emit(
            "thread-lifecycle", "populate_scan_image_gallery.enter",
            panel=id(self), tid=threading.get_ident(), directory=directory,
            emit_signal=emit_signal, remaining_ms=_remaining_ms,
        )
        if _remaining_ms > 0:
            QTimer.singleShot(
                _remaining_ms,
                lambda: self.populate_scan_image_gallery(directory, emit_signal),
            )
            return

        self._scan_pipeline_busy = True
        QTimer.singleShot(10_000, self._scan_pipeline_watchdog)

        # Stop and drain scanner threads on THIS instance and every linked
        # peer (Wallpaper's System-Display/Monitor-Display panels share a
        # mutable _initial_pixmap_cache dict -- see wallpaper_tab.py -- and
        # populate_scan_image_gallery(emit_signal=True) synchronously calls
        # into each linked peer's own populate_scan_image_gallery() below,
        # via directory_scanned). Doing this for every linked instance
        # up front, before either side clears its cache or tears down
        # widgets, closes a cross-panel instance of the same
        # deleteOrphaned/use-after-free race this method already guards
        # against for its own, single-instance case.
        self._stop_scanner_threads()
        for peer in getattr(self, "linked_tabs", []):
            # Addendum 21 (.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md):
            # a live, telemetry+hs_err-correlated SIGSEGV inside
            # QObjectPrivate::ConnectionData::deleteOrphaned localized to
            # exactly this reentrant path -- if *peer* is itself mid-flight
            # through its own populate_scan_image_gallery() call (for a
            # different, newer switch than the one that call originally
            # started for), that call already did (or, since it hasn't
            # returned yet, still will) call ITS OWN _stop_scanner_threads()
            # as its own very first step. Reaching into it again from here
            # is redundant at best, and empirically correlated with the
            # crash: peer's own in-flight teardown/rebuild can have
            # freshly-constructed QObjects and/or freshly-queued
            # deleteLater() calls on the stack at the exact moment this
            # call's own _stop_scanner_threads() fires ITS process-wide
            # (receiver=None) DeferredDelete flush -- a global flush
            # triggered from a completely different call stack, landing in
            # the middle of unrelated in-progress teardown/construction.
            # peer's own call remains solely responsible for its own
            # scanner-thread lifecycle while _scan_pipeline_busy is set.
            if getattr(peer, "_scan_pipeline_busy", False):
                telemetry.emit(
                    "thread-lifecycle", "stop_scanner_threads.peer_skip_busy",
                    panel=id(self), peer=id(peer),
                )
                continue
            if hasattr(peer, "_stop_scanner_threads"):
                peer._stop_scanner_threads()

        self.scanned_dir = directory
        path_edit = getattr(self, "scan_directory_path", None)
        if path_edit is not None:
            path_edit.setText(directory)

        if emit_signal:
            self.directory_scanned.emit(directory)

        self.clear_gallery_widgets()
        self.path_to_label_map.clear()
        self._initial_pixmap_cache.clear()
        self.cancel_loading()
        self.gallery_image_paths = []
        # Unconditional reset (Addendum 25): previously only reset via the
        # side effect of start_loading_gallery(append=False) below, which
        # is itself gated on quick_paths being non-empty -- a directory
        # with no images (a video-only directory, now that video scanning
        # populates the gallery too) left this holding the PREVIOUS
        # directory's paths, which _on_video_scan_finished's
        # start_loading_gallery(..., append=True) would then extend
        # instead of replace: old thumbnails bleeding into the new
        # directory, and duplicating on every re-scan of the same
        # video-only directory.
        self.master_image_paths = []

        try:
            entries = sorted(
                os.scandir(directory), key=lambda e: natural_sort_key(e.name)
            )
            valid_exts = tuple(
                f".{fmt.lower().lstrip('.')}" for fmt in SUPPORTED_IMG_FORMATS
            )
            quick_paths = [
                e.path
                for e in entries
                if e.is_file() and e.name.lower().endswith(valid_exts)
            ]
            quick_paths_limited = quick_paths[:5000]
            if quick_paths_limited:
                self.start_loading_gallery(
                    quick_paths_limited, show_progress=False, append=False
                )
        except Exception:
            pass

        self.img_scanner_worker = ImageScannerWorker(directory)
        self.img_scanner_thread = self.img_scanner_worker

        # Bind the worker instance into the connection itself (rather than
        # relying on QObject.sender() inside the slot) so a stale delivery
        # can be identified even after the sender's C++ object has already
        # been destroyed -- see _on_image_scan_finished()'s docstring.
        self.img_scanner_worker.scan_finished.connect(
            lambda paths, _worker=self.img_scanner_worker: self._on_image_scan_finished(
                paths, _worker
            )
        )
        # Same stale-delivery guard as scan_finished above: an old scanner's
        # queued scan_error can still arrive after a newer directory switch
        # replaced self.img_scanner_worker; handle_scan_error() tears down
        # gallery widgets unconditionally, which would otherwise do so for
        # whatever directory is now current, not the one that actually errored.
        self.img_scanner_worker.scan_error.connect(
            lambda message, _worker=self.img_scanner_worker: self.handle_scan_error(message, _worker)
        )

        self.img_scanner_worker.finished.connect(self.img_scanner_worker.deleteLater)
        self.img_scanner_worker.finished.connect(
            lambda: setattr(self, "img_scanner_thread", None)
        )
        print(
            f"[thread-lifecycle] panel={id(self):x} img_thread={id(self.img_scanner_worker):x} "
            f"tid={threading.get_ident()} starting ImageScannerWorker for {directory!r}",
            flush=True,
        )
        telemetry.emit(
            "thread-lifecycle", "img_worker.start.begin",
            panel=id(self), img_thread=id(self.img_scanner_worker),
            tid=threading.get_ident(), directory=directory,
        )
        self.img_scanner_worker.start()
        print(
            f"[thread-lifecycle] panel={id(self):x} img_thread={id(self.img_scanner_worker):x} "
            f"start() returned",
            flush=True,
        )
        telemetry.emit(
            "thread-lifecycle", "img_worker.start.returned",
            panel=id(self), img_thread=id(self.img_scanner_worker),
            tid=threading.get_ident(),
        )

    def _on_image_scan_finished(self, image_paths: list, _worker=None):
        # scan_finished is delivered via a queued cross-thread connection,
        # so it can arrive AFTER a newer populate_scan_image_gallery() call
        # already replaced self.img_scanner_worker/self.img_scanner_thread
        # with a fresh scan for a different directory (rapid directory
        # switching -- e.g. via the QApplication.sendPostedEvents() flush
        # in _stop_scanner_threads() reentrantly pumping this queued signal
        # mid-teardown, or simply because the event loop hadn't gotten to
        # it yet by the time the user switched again). Acting on a stale
        # result here would touch gallery state for a directory the user
        # has already navigated away from -- the actual mechanism behind
        # the deleteOrphaned crash class recurring even after the round-9
        # fix (see Addendum 9 in
        # .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md).
        #
        # _worker identifies the emitting worker via the connection's own
        # closure (bound in populate_scan_image_gallery()), not via
        # QObject.sender(): a superseded worker's C++ object may already
        # be destroyed (deleteLater() already flushed by a later switch's
        # _stop_scanner_threads()) by the time its queued scan_finished is
        # actually processed, and sender() returns None for a destroyed
        # sender -- silently defeating a sender()-based staleness check
        # for exactly the stale deliveries it needs to catch. Comparing
        # the captured Python object reference by identity needs no
        # access to the (possibly-destroyed) C++ side at all.
        _current_id_str = f"{id(self.img_scanner_worker):x}" if self.img_scanner_worker is not None else "none"
        _worker_id_str = f"{id(_worker):x}" if _worker is not None else "none"
        if _worker is not None and _worker is not self.img_scanner_worker and _worker is not self.img_scanner_thread:
            print(
                f"[thread-lifecycle] panel={id(self):x} tid={threading.get_ident()} "
                f"_on_image_scan_finished: STALE delivery from worker={_worker_id_str}, "
                f"current={_current_id_str}, ignoring",
                flush=True,
            )
            telemetry.emit(
                "thread-lifecycle", "on_image_scan_finished.stale",
                panel=id(self), tid=threading.get_ident(),
                worker=_worker_id_str, current=_current_id_str,
            )
            return
        print(
            f"[thread-lifecycle] panel={id(self):x} tid={threading.get_ident()} "
            f"_on_image_scan_finished: proceeding, worker={_worker_id_str}",
            flush=True,
        )
        telemetry.emit(
            "thread-lifecycle", "on_image_scan_finished.proceeding",
            panel=id(self), tid=threading.get_ident(), worker=_worker_id_str,
            image_count=len(image_paths),
        )

        existing_paths = set(getattr(self, "master_image_paths", []))
        new_paths = [p for p in image_paths if p not in existing_paths]

        if new_paths:
            self.start_loading_gallery(new_paths, show_progress=False, append=True)
        else:
            self.refresh_gallery_view()

        if self.gallery_image_paths:
            self.gallery_image_paths.sort(key=natural_sort_key)
            self.refresh_gallery_view()

        self._start_video_scan(self.scanned_dir)

    def _start_video_scan(self, directory: str) -> None:
        """Second phase of the scan pipeline, run strictly after the image
        scan above has settled -- see this module's docstring."""
        self.vid_scanner_worker = VideoScannerWorker(directory)
        self.vid_scanner_thread = self.vid_scanner_worker

        self.vid_scanner_worker.scan_finished.connect(
            lambda paths, _worker=self.vid_scanner_worker: self._on_video_scan_finished(
                paths, _worker
            )
        )
        self.vid_scanner_worker.scan_error.connect(
            lambda message, _worker=self.vid_scanner_worker: self._on_video_scan_error(_worker)
        )
        self.vid_scanner_worker.finished.connect(self.vid_scanner_worker.deleteLater)
        self.vid_scanner_worker.finished.connect(
            lambda: setattr(self, "vid_scanner_thread", None)
        )
        telemetry.emit(
            "thread-lifecycle", "vid_worker.start.begin",
            panel=id(self), vid_thread=id(self.vid_scanner_worker),
            tid=threading.get_ident(), directory=directory,
        )
        self.vid_scanner_worker.start()

    def _on_video_scan_finished(self, video_paths: list, _worker=None) -> None:
        # Same staleness guard as _on_image_scan_finished -- see its
        # docstring for the full rationale (identity comparison via the
        # closure-bound worker, not sender(), since a superseded worker's
        # C++ object may already be destroyed by the time this queued
        # signal is actually processed).
        if _worker is not None and _worker is not self.vid_scanner_worker and _worker is not self.vid_scanner_thread:
            telemetry.emit(
                "thread-lifecycle", "on_video_scan_finished.stale",
                panel=id(self), tid=threading.get_ident(),
            )
            return

        if video_paths:
            # Same dedup as _on_image_scan_finished's new_paths filter --
            # belt-and-suspenders alongside the unconditional
            # master_image_paths reset in populate_scan_image_gallery()
            # above: never append a path start_loading_gallery(append=True)
            # would otherwise duplicate.
            existing_paths = set(getattr(self, "master_image_paths", []))
            new_video_paths = [p for p in video_paths if p not in existing_paths]
            if new_video_paths:
                self.start_loading_gallery(new_video_paths, show_progress=False, append=True)
            if self.gallery_image_paths:
                self.gallery_image_paths.sort(key=natural_sort_key)
                self.refresh_gallery_view()

        self._settle_scan_pipeline()

    def _on_video_scan_error(self, _worker=None) -> None:
        # Unlike handle_scan_error() for the image phase, a video-scan
        # error doesn't tear down gallery widgets (the image gallery is
        # already showing valid content by this point) -- just settle the
        # pipeline so the next queued switch, if any, can proceed.
        if _worker is not None and _worker is not self.vid_scanner_worker and _worker is not self.vid_scanner_thread:
            return
        self._settle_scan_pipeline()

    def _settle_scan_pipeline(self) -> None:
        """Marks the current directory switch's scan pipeline as finished
        and, if a newer switch was requested while this one was still in
        flight, kicks it off now. See populate_scan_image_gallery()'s
        serialization comment."""
        self._scan_pipeline_busy = False
        pending = getattr(self, "_pending_scan_request", None)
        if pending is not None:
            self._pending_scan_request = None
            directory, emit_signal = pending
            QTimer.singleShot(0, lambda: self.populate_scan_image_gallery(directory, emit_signal))

    def _scan_pipeline_watchdog(self) -> None:
        """Safety net: force-clears a stuck _scan_pipeline_busy flag. Should
        never actually fire in practice (_on_image_scan_finished()/
        handle_scan_error() clear it on every real exit path from the scan
        pipeline) -- exists so a missed edge case degrades to "an overlap
        can occur" (the pre-existing, individually-guarded behavior) rather
        than "every future switch on this instance silently does nothing"."""
        if getattr(self, "_scan_pipeline_busy", False):
            self._settle_scan_pipeline()


__all__ = ["_ScanPipelineMixin"]
