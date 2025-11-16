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
            if self.config.get("screenshot_dir"):
                os.makedirs(self.config["screenshot_dir"], exist_ok=True)
                
            # --- FIX: Passing the entire config dictionary ---
            crawler = ImageCrawler(self.config)
            # --- END FIX ---

            downloaded = 0
            def on_saved(path):
                nonlocal downloaded
                downloaded += 1
                self.status.emit(f"Saved: {os.path.basename(path)}")

            # Note: on_progress signal removed from crawler logic, only using status
            crawler.on_status.connect(self.status.emit)
            crawler.on_image_saved.connect(on_saved)

            self.status.emit("Starting crawl...")
            crawler.run()

            self.finished.emit(downloaded, f"Downloaded {downloaded} image(s)!")

        except Exception as e:
            self.error.emit(str(e))
