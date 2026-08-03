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


__all__ = ["MediaLoaderWorker"]
