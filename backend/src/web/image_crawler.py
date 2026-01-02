import os
import json
import base # Native extension
from PySide6.QtCore import QObject, Signal

class ImageCrawler(QObject):
    """
    Advanced Image Crawler that interprets action sequences.
    Now acts as a wrapper for the Rust implementation.
    """

    on_status = Signal(str)
    on_image_saved = Signal(str)
    on_finished = Signal(str)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self._is_running = True

    def stop(self):
        self._is_running = False
        self.on_status.emit("Cancellation pending...")

    def on_status_emitted(self, msg: str):
        self.on_status.emit(msg)

    def run(self):
        config_json = json.dumps(self.config)
        try:
            total = base.run_image_crawler(config_json, self)
            self.on_finished.emit(f"Finished. Downloaded {total} images.")
            return total
        except Exception as e:
            self.on_error_emitted(f"Critical error in Rust crawler: {e}")
            self.on_finished.emit(f"Finished with error: {e}")
            return 0

    def on_error_emitted(self, msg: str):
        self.on_status.emit(f"ERROR: {msg}")
