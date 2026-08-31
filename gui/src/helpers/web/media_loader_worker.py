"""Runs a source-specific downloader off the UI thread.

This is a main-thread ``QObject`` plus a plain ``threading.Thread``. It is
deliberately **not** a ``QThread``.

Why: constructing ``NhentaiDownloader`` / ``RedditDownloader`` (QObjects)
inside ``QThread.run()`` instantiates Qt's per-thread event dispatcher —
a glib ``QSocketNotifier`` on a wake-up pipe. The downloader then opens
many Python ``requests`` sockets; those fds reuse the dispatcher's closed
pipe numbers. The GUI thread later enables/disables the stale notifier
(``QSocketNotifier: Socket notifiers cannot be enabled or disabled from
another thread`` / ``Invalid socket N``) and glibc aborts with
``corrupted size vs. prev_size`` under the live JPype JVM.

Python reports that native ``QThread`` as ``Dummy-N`` (a ``_DummyThread``).
That is not a ``ThreadPoolExecutor`` worker.

The downloader QObject is therefore created on the same thread as this
worker (the GUI thread). Only the already-documented-safe blocking
``downloader.run()`` runs on the worker thread. ``Signal.emit()`` is
thread-safe and queues to the GUI-thread receivers.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

from backend.src.web import (
    NhentaiDownloader,
    RedditDownloader,
)
from PySide6.QtCore import QObject, Signal

from gui.src.helpers.gc_safe import gc_disabled_run


class MediaLoaderWorker(QObject):
    """Runs a source-specific downloader (Reddit, nhentai, ...) off the UI thread."""

    status = Signal(str)
    sig_finished = Signal(int, str)
    error = Signal(str)
    media_saved = Signal(str)

    def __init__(self, source: str, config: dict, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.source = source
        self.config = config
        self._downloader = None
        self._thread: Optional[threading.Thread] = None

    def isRunning(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Spawn the worker thread. Constructs the downloader on *this* thread."""
        if self.isRunning():
            return
        self._ensure_downloader()
        self._thread = threading.Thread(
            target=self.run,
            name="media-loader",
            daemon=True,
        )
        self._thread.start()

    def wait(self, msec: int = 30000) -> bool:
        """Block until the worker thread finishes. ``msec < 0`` waits forever."""
        if self._thread is None:
            return True
        timeout = None if msec < 0 else msec / 1000.0
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def cancel(self) -> None:
        if self._downloader is not None:
            self._downloader.stop()

    def stop(self) -> None:
        """Request cancel. Tests and subclasses may override."""
        self.cancel()

    def _ensure_downloader(self):
        if self._downloader is not None:
            return
        if self.source == "reddit":
            downloader = RedditDownloader(self.config)
        elif self.source == "nhentai":
            downloader = NhentaiDownloader(self.config)
        else:
            return
        downloader.on_status.connect(self.status.emit)
        downloader.on_image_saved.connect(self.media_saved.emit)
        downloader.on_finished.connect(self.sig_finished.emit)
        downloader.on_error.connect(self.error.emit)
        self._downloader = downloader

    @gc_disabled_run
    def run(self) -> None:
        try:
            os.makedirs(self.config["download_dir"], exist_ok=True)

            if self.source not in ("reddit", "nhentai"):
                self.error.emit(f"Unknown media source: {self.source}")
                return

            # Sync test path calls run() on the GUI thread without start().
            # start() already constructed the downloader on the GUI thread
            # before spawning -- never construct it here if we are on the
            # worker thread (that is the crash this module exists to avoid).
            if self._downloader is None:
                if (
                    self._thread is not None
                    and threading.current_thread() is self._thread
                ):
                    self.error.emit(
                        "Internal error: downloader must be constructed on the GUI thread"
                    )
                    return
                self._ensure_downloader()

            if self._downloader is None:
                self.error.emit(f"Unknown media source: {self.source}")
                return

            self.status.emit(f"Starting {self.source} download...")
            self._downloader.run()
        except Exception as e:
            self.error.emit(f"Critical Worker Error: {e}")


__all__ = ["MediaLoaderWorker"]
