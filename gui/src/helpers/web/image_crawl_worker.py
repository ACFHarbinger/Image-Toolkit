import os

from PySide6.QtCore import QThread, Signal
from backend.src.web import (
    ImageCrawler,
    DanbooruCrawler,
    GelbooruCrawler,
    SankakuCrawler,
)


class ImageCrawlWorker(QThread):
    progress = Signal(int, int)  # (current, total)
    status = Signal(str)  # status message
    finished = Signal(int, str)  # (count, message)
    error = Signal(str)  # error message

    def __init__(self, config: dict):
        super().__init__()
        self.config = config

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

            downloaded = 0

            def on_saved(path):
                nonlocal downloaded
                downloaded += 1
                self.status.emit(f"Saved: {os.path.basename(path)}")

            # Connect signals
            crawler.on_status.connect(self.status.emit)
            crawler.on_image_saved.connect(on_saved)

            self.status.emit(f"Starting {crawler_type.title()} Crawl...")

            # Run the crawler
            final_count = crawler.run()

            # Fallback if the crawler doesn't return a count
            if final_count is None:
                final_count = downloaded

            self.finished.emit(
                final_count, f"Crawl finished. Downloaded **{final_count}** image(s)!"
            )

        except Exception as e:
            self.error.emit(f"Critical Worker Error: {e}")
