import json

import base  # Native extension

from backend.src.events import Observable


class WebRequestsLogic:
    """
    Wrapper for the C++ implementation of WebRequestsLogic.
    Uses 'base.run_web_requests_sequence' for the heavy lifting.
    """

    def __init__(self, config: dict):
        self.config = config
        self._is_running = True
        # === Events (issue #529: plain Observables, not Qt signals) ===
        self.on_status: Observable[str] = Observable()
        self.on_error: Observable[str] = Observable()
        self.on_finished: Observable[str] = Observable()

    def stop(self):
        """Sets the flag to stop the execution loop."""
        self._is_running = False
        self.on_status.publish("Cancellation pending...")

    def on_status_emitted(self, msg: str):
        """Glue method called by C++ to emit on_status signal."""
        self.on_status.publish(msg)

    def on_error_emitted(self, msg: str):
        """Glue method called by C++ to emit on_error signal."""
        self.on_error.publish(msg)

    def run(self):
        """
        Main execution loop delegate.
        Sends the config as JSON to C++.
        """
        config_json = json.dumps(self.config)

        try:
            result = base.run_web_requests_sequence(config_json, self)
            if self._is_running:
                self.on_finished.publish(result)
        except Exception as e:
            self.on_error.publish(f"Critical error in C++ sequence: {e}")
            self.on_finished.publish(f"Finished with error: {e}")
