import os

from backend.src.web import (
    NhentaiDownloader,
    RedditDownloader,
)
from PySide6.QtCore import QThread, Signal


class MediaLoaderWorker(QThread):
    """Runs a source-specific downloader (Reddit, nhentai, ...) off the UI thread."""

    status = Signal(str)
    sig_finished = Signal(int, str)
    error = Signal(str)
    media_saved = Signal(str)

    def __init__(self, source: str, config: dict):
        super().__init__()
        self.source = source
        self.config = config
        self._downloader = None

    def cancel(self) -> None:
        if self._downloader is not None:
            self._downloader.stop()

    def run(self) -> None:
        downloader = None
        try:
            os.makedirs(self.config["download_dir"], exist_ok=True)

            if self.source == "reddit":
                downloader = RedditDownloader(self.config)
            elif self.source == "nhentai":
                downloader = NhentaiDownloader(self.config)
            else:
                self.error.emit(f"Unknown media source: {self.source}")
                return

            self._downloader = downloader
            downloader.on_status.connect(self.status.emit)
            downloader.on_image_saved.connect(self.media_saved.emit)
            # Connected before run() -- run() is synchronous and blocks
            # until the downloader emits on_finished internally, so
            # connecting afterwards would always miss the signal.
            downloader.on_finished.connect(self.sig_finished.emit)
            downloader.on_error.connect(self.error.emit)

            self.status.emit(f"Starting {self.source} download...")
            downloader.run()
        except Exception as e:
            self.error.emit(f"Critical Worker Error: {e}")
        finally:
            # The downloader is a QObject created in THIS worker thread
            # (its thread affinity is the worker thread). Drop the only
            # remaining reference here, on the worker thread, so its C++
            # object is destroyed from the thread that owns it -- NOT from
            # the main thread later, when the tab's next Download click
            # replaces self.worker and Python GC destroys the old QThread.
            # Destroying a worker-thread QObject from the main thread is
            # the cross-thread destruction behind the recurring
            # QObject::killTimer / Shiboken retrieveWrapper /
            # QObject::property SIGSEGVs when Download is clicked twice.
            self._downloader = None
            downloader = None


__all__ = ["MediaLoaderWorker"]
