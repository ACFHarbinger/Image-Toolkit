import os

from PySide6.QtCore import QThread, Signal
from backend.src.web.image_crawler import ImageCrawler


class ImageCrawlWorker(QThread):
    progress = Signal(int, int)      # (current, total)
    status = Signal(str)             # status message
    finished = Signal(int, str)      # (count, message)
    error = Signal(str)              # error message

    def __init__(self, config: dict):
        super().__init__()
        self.config = config

    def run(self):
        try:
            # Create download directory, and screenshot directory if provided
            os.makedirs(self.config["download_dir"], exist_ok=True)
            if self.config["screenshot_dir"]:
                os.makedirs(self.config["screenshot_dir"], exist_ok=True)
                
            crawler = ImageCrawler(
                url=self.config["url"],
                headless=self.config["headless"],
                download_dir=self.config["download_dir"],
                browser=self.config["browser"],
                # --- NEW ARGUMENTS ---
                screenshot_dir=self.config["screenshot_dir"], 
                skip_first=self.config["skip_first"],
                skip_last=self.config["skip_last"]
            )

            downloaded = 0
            def on_saved(path):
                nonlocal downloaded
                downloaded += 1
                self.status.emit(f"Saved: {os.path.basename(path)}")

            crawler.on_progress.connect(lambda c, t: self.progress.emit(c, t))
            crawler.on_status.connect(self.status.emit)
            crawler.on_image_saved.connect(on_saved)

            self.status.emit("Starting crawl...")
            crawler.run()

            self.finished.emit(downloaded, f"Downloaded {downloaded} image(s)!")

        except Exception as e:
            self.error.emit(str(e))
