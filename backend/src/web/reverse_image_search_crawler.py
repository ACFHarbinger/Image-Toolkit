import json
import base  # Native extension
from typing import List, Dict
from PySide6.QtCore import QObject, Signal


class ReverseImageSearchCrawler(QObject):
    """
    A specialized crawler that performs reverse image searches using Google Lens.
    Now acts as a wrapper for the Rust implementation.
    """

    on_status = Signal(str)

    def __init__(
        self, headless=True, download_dir=None, screenshot_dir=None, browser="brave"
    ):
        super().__init__()
        self.headless = headless
        self.download_dir = download_dir
        self.screenshot_dir = screenshot_dir
        self.browser = browser
        self._is_running = True

    def stop(self):
        self._is_running = False
        self.on_status.emit("Cancellation pending...")

    def on_status_emitted(self, msg: str):
        self.on_status.emit(msg)

    def perform_reverse_search(
        self,
        image_path: str,
        min_width: int = 0,
        min_height: int = 0,
        search_mode: str = "All",
    ) -> List[Dict[str, str]]:

        config = {
            "headless": self.headless,
            "image_path": image_path,
            "search_mode": search_mode,
            "browser": self.browser,
        }

        try:
            results_json = base.run_reverse_image_search(json.dumps(config), self)
            results = json.loads(results_json)

            # Filter by resolution if needed (resolution is currently "Unknown" in Rust)
            final_results = []
            for r in results:
                # In Rust we didn't implement resolution scraping yet, but we can if needed
                final_results.append(r)

            return final_results
        except Exception as e:
            self.on_status.emit(f"Critical error in Rust search: {e}")
            return []

    def close(self):
        pass
