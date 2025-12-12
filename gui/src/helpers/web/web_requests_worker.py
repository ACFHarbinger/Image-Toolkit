from PySide6.QtCore import QThread, Signal
from backend.src.web import WebRequestsLogic


class WebRequestsWorker(QThread):
    status = Signal(str)  # status message
    finished = Signal(str)  # (message)
    error = Signal(str)  # error message

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.logic = None

    def run(self):
        try:
            self.logic = WebRequestsLogic(self.config)

            # Connect signals from logic to worker's signals
            self.logic.on_status.connect(self.status.emit)
            self.logic.on_error.connect(self.error.emit)
            self.logic.on_finished.connect(self.finished.emit)

            self.status.emit("Starting requests...")

            # Run the main logic
            self.logic.run()

        except Exception as e:
            self.error.emit(f"Critical Worker Error: {e}")
            self.finished.emit(f"Error: {e}")

    def stop(self):
        """
        Signals the logic class to stop processing if it's running.
        """
        if self.logic:
            self.logic.stop()
        self.status.emit("Stop signal sent to logic.")
