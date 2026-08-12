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


class ImageCrawlWorker(QThread):
    progress = Signal(int, int)  # (current, total)
    status = Signal(str)  # status message
    sig_finished = Signal(int, str)  # (count, message)
    error = Signal(str)  # error message
    image_downloaded = Signal(str)  # saved file path

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.crawler = None

    def stop(self):
        """Stop the underlying crawler instance and interrupt thread."""
        if self.crawler:
            with contextlib.suppress(Exception):
                self.crawler.stop()
        self.requestInterruption()

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

            downloaded = 0

            def on_saved(meta_or_path):
                nonlocal downloaded
                downloaded += 1
                if isinstance(meta_or_path, str) and meta_or_path.startswith("{"):
                    with contextlib.suppress(Exception):
                        meta = json.loads(meta_or_path)
                        path = meta["path"]
                        global_id = meta.get("global_id", downloaded)
                        page_num = meta.get("page_num", 1)
                        pos_on_page = meta.get("index_on_page", downloaded)
                        self.status.emit(
                            f"Saved [{global_id}] (Page {page_num} #{pos_on_page}): {os.path.basename(path)}"
                        )
                        self.image_downloaded.emit(meta)
                        return

                path = meta_or_path if isinstance(meta_or_path, str) else str(meta_or_path)
                self.status.emit(f"Saved: {os.path.basename(path)}")
                self.image_downloaded.emit(path)

            # Connect signals
            crawler.on_status.connect(self.status.emit)
            crawler.on_image_saved.connect(on_saved)

            self.status.emit(f"Starting {crawler_type.title()} Crawl...")

            # Run the crawler
            final_count = crawler.run()

            # Fallback if the crawler doesn't return a count
            if final_count is None:
                final_count = downloaded

            self.sig_finished.emit(
                final_count, f"Crawl finished. Downloaded **{final_count}** image(s)!"
            )

        except Exception as e:
            self.error.emit(f"Critical Worker Error: {e}")
