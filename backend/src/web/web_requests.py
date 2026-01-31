import json
import base  # Native extension

from PySide6.QtCore import QObject, Signal


class WebRequestsLogic(QObject):
    """
    Wrapper for the Rust implementation of WebRequestsLogic.
    Uses 'base.run_web_requests_sequence' for the heavy lifting.
    """

    # === SIGNALS ===
    on_status = Signal(str)
    on_error = Signal(str)
    on_finished = Signal(str)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self._is_running = True

    def stop(self):
        """Sets the flag to stop the execution loop."""
        self._is_running = False
        self.on_status.emit("Cancellation pending...")

    def on_status_emitted(self, msg: str):
        """Glue method called by Rust to emit on_status signal."""
        self.on_status.emit(msg)

    def on_error_emitted(self, msg: str):
        """Glue method called by Rust to emit on_error signal."""
        self.on_error.emit(msg)

    def run(self):
        """
        Main execution loop delegate.
        Sends the config as JSON to Rust.
        """
        config_json = json.dumps(self.config)

        try:
            result = base.run_web_requests_sequence(config_json, self)
            if self._is_running:
                self.on_finished.emit(result)
        except Exception as e:
            self.on_error.emit(f"Critical error in Rust sequence: {e}")
            self.on_finished.emit(f"Finished with error: {e}")
