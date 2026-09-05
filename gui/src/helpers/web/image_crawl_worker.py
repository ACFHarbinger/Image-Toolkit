import contextlib
import json
import os

from backend.src.web import (
    DanbooruCrawler,
    GelbooruCrawler,
    ImageCrawler,
    SankakuCrawler,
)
from PySide6.QtCore import QThread, Signal

from gui.src.helpers.gc_safe import gc_disabled_run
from gui.src.qt_event_bridge import QtEventBridge


class ImageCrawlWorker(QThread):
    progress = Signal(int, int)  # (current, total)
    status = Signal(str)  # status message
    sig_finished = Signal(int, str)  # (count, message)
    error = Signal(str)  # error message
    image_downloaded = Signal(str)  # saved file path or JSON-encoded metadata string

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.crawler = None
        self._downloaded = 0
        # Bridges are QObjects: construct here on the GUI thread, attach in
        # run() once the crawler exists (issue #529).
        self._status_bridge = QtEventBridge(self.status.emit, parent=self)
        self._saved_bridge = QtEventBridge(self._on_image_saved, parent=self)

    def _on_image_saved(self, meta_or_path) -> None:
        self._downloaded += 1

        # Backend emits json.dumps(meta); parse only for status log display.
        # Always re-emit as a str — Signal(str) works safely across threads.
        if isinstance(meta_or_path, str) and meta_or_path.strip().startswith("{"):
            with contextlib.suppress(Exception):
                meta = json.loads(meta_or_path)
                path = meta.get("path", "")
                global_id = meta.get("global_id", self._downloaded)
                page_num = meta.get("page_num", 1)
                pos_on_page = meta.get("index_on_page", self._downloaded)
                self.status.emit(
                    f"Saved [{global_id}] (Page {page_num} #{pos_on_page}): {os.path.basename(path)}"
                )
            self.image_downloaded.emit(meta_or_path)
            return

        path = meta_or_path if isinstance(meta_or_path, str) else str(meta_or_path)
        self.status.emit(f"Saved: {os.path.basename(path)}")
        self.image_downloaded.emit(path)

    def stop(self):
        """Stop the underlying crawler instance and interrupt thread."""
        if self.crawler:
            with contextlib.suppress(Exception):
                self.crawler.stop()
        self.requestInterruption()

    @gc_disabled_run
    def run(self):
        try:
            # Create download directory, and screenshot directory if provided
            os.makedirs(self.config["download_dir"], exist_ok=True)
            if self.config.get("screenshot_dir"):
                os.makedirs(self.config["screenshot_dir"], exist_ok=True)

            crawler_type = self.config.get("type", "general")

            if crawler_type == "board":
                board_type = self.config.get("board_type", "danbooru")
                if board_type == "gelbooru":
                    crawler = GelbooruCrawler(self.config)
                elif board_type == "sankaku":
                    crawler = SankakuCrawler(self.config)
                else:  # defaults to danbooru
                    crawler = DanbooruCrawler(self.config)
            else:
                crawler = ImageCrawler(self.config)

            self.crawler = crawler
            self._downloaded = 0

            # Bridge backend Observables onto the GUI thread (issue #529).
            self._status_bridge.attach(crawler.on_status)
            self._saved_bridge.attach(crawler.on_image_saved)
            try:
                self.status.emit(f"Starting {crawler_type.title()} Crawl...")

                # Run the crawler
                final_count = crawler.run()

                # Fallback if the crawler doesn't return a count
                if final_count is None:
                    final_count = self._downloaded

                self.sig_finished.emit(
                    final_count, f"Crawl finished. Downloaded **{final_count}** image(s)!"
                )

            finally:
                self._status_bridge.detach()
                self._saved_bridge.detach()

        except Exception as e:
            self.error.emit(f"Critical Worker Error: {e}")
