import json
import base  # Native extension
from PySide6.QtCore import QObject, Signal


class ImageBoardCrawler(QObject):
    """
    Abstract Base Class for Image Board Crawlers.
    Now acts as a wrapper for the Rust implementation.
    """

    # === SIGNALS ===
    on_status = Signal(str)  # status message
    on_image_saved = Signal(str)  # saved file path

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self._is_running = True

    def stop(self):
        """Sets the flag to stop the execution loop."""
        self._is_running = False
        self.on_status.emit("Crawl cancellation pending...")

    def on_status_emitted(self, msg: str):
        """Glue method called by Rust to emit on_status signal."""
        self.on_status.emit(msg)

    def run(self):
        """
        Main execution loop delegate.
        Calls the Rust implementation via base.run_board_crawler.
        """
        crawler_name = self.__class__.__name__.replace("Crawler", "").lower()
        config_json = json.dumps(self.config)

        try:
            total_downloaded = base.run_board_crawler(crawler_name, config_json, self)
            return total_downloaded
        except Exception as e:
            self.on_status.emit(f"Critical Error in Rust crawler: {str(e)}")
            return 0
