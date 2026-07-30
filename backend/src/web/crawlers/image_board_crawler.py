import json
import time
from typing import Dict

import base  # Native extension
from PySide6.QtCore import QObject, Signal


class ImageBoardCrawler(QObject):
    """
    Abstract Base Class for Image Board Crawlers.
    Now acts as a wrapper for the C++ implementation.
    """

    # === SIGNALS ===
    on_status = Signal(str)  # status message
    on_image_saved = Signal(str)  # saved file path

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self._is_running = True
        # §12.7 (issue #70) — per-crawl telemetry. The C++ extension
        # (base.run_board_crawler) makes the actual HTTP requests and only
        # calls back into Python via on_image_saved (one per successful
        # download, base/src/web/board_crawler.cpp:125) and on_status_emitted
        # (free-form progress strings, no structured response-code field) —
        # there is no per-request hook exposed across the pybind boundary, so
        # "per-request timing and response-code tracking" as literally
        # specced isn't available from Python. What's built here instead:
        # whole-crawl timing/throughput (elapsed_sec, images_per_sec — exact,
        # from the real on_image_saved count) plus best-effort timeout/CAPTCHA
        # counters derived by substring-matching on_status messages (coarse —
        # only as good as whatever text the C++ side happens to emit, not a
        # real response-code count).
        self.telemetry: Dict = {
            "images_saved": 0,
            "status_messages": 0,
            "timeout_count": 0,
            "captcha_count": 0,
            "error_count": 0,
            "elapsed_sec": None,
            "images_per_sec": None,
        }
        self.on_image_saved.connect(self._record_image_saved)
        self.on_status.connect(self._record_status_message)

    def _record_image_saved(self, _path: str) -> None:
        self.telemetry["images_saved"] += 1

    def _record_status_message(self, msg: str) -> None:
        self.telemetry["status_messages"] += 1
        low = msg.lower()
        if "timeout" in low or "timed out" in low:
            self.telemetry["timeout_count"] += 1
        if "captcha" in low:
            self.telemetry["captcha_count"] += 1
        if "error" in low or "critical" in low:
            self.telemetry["error_count"] += 1

    def stop(self):
        """Sets the flag to stop the execution loop."""
        self._is_running = False
        self.on_status.emit("Crawl cancellation pending...")

    def on_status_emitted(self, msg: str):
        """Glue method called by C++ to emit on_status signal."""
        self.on_status.emit(msg)

    def run(self):
        """
        Main execution loop delegate.
        Calls the C++ implementation via base.run_board_crawler.
        """
        crawler_name = self.__class__.__name__.replace("Crawler", "").lower()
        selection_mode = self.config.get("selection_mode", "Download All (Default)")
        self.on_status.emit(f"Crawl starting with selection mode: {selection_mode}")
        config_json = json.dumps(self.config)

        t0 = time.perf_counter()
        try:
            total_downloaded = base.run_board_crawler(crawler_name, config_json, self)
            return total_downloaded
        except Exception as e:
            self.on_status.emit(f"Critical Error in C++ crawler: {str(e)}")
            return 0
        finally:
            elapsed = time.perf_counter() - t0
            self.telemetry["elapsed_sec"] = round(elapsed, 3)
            if elapsed > 0:
                self.telemetry["images_per_sec"] = round(
                    self.telemetry["images_saved"] / elapsed, 3
                )
