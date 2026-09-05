from backend.src.web import WebRequestsLogic
from PySide6.QtCore import QThread, Signal

from gui.src.helpers.gc_safe import gc_disabled_run
from gui.src.qt_event_bridge import QtEventBridge


class WebRequestsWorker(QThread):
    status = Signal(str)  # status message
    sig_finished = Signal(str)  # (message)
    error = Signal(str)  # error message

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.logic = None
        # Bridges are QObjects: construct here on the GUI thread, attach in
        # run() once the logic object exists (issue #529).
        self._status_bridge = QtEventBridge(self.status.emit, parent=self)
        self._error_bridge = QtEventBridge(self.error.emit, parent=self)
        self._finished_bridge = QtEventBridge(self.sig_finished.emit, parent=self)

    @gc_disabled_run
    def run(self):
        try:
            self.logic = WebRequestsLogic(self.config)

            # Bridge backend Observables onto the GUI thread (issue #529).
            self._status_bridge.attach(self.logic.on_status)
            self._error_bridge.attach(self.logic.on_error)
            self._finished_bridge.attach(self.logic.on_finished)
            try:
                self.status.emit("Starting requests...")

                # Run the main logic
                self.logic.run()

            finally:
                self._status_bridge.detach()
                self._error_bridge.detach()
                self._finished_bridge.detach()

        except Exception as e:
            self.error.emit(f"Critical Worker Error: {e}")
            self.sig_finished.emit(f"Error: {e}")

    def stop(self):
        """
        Signals the logic class to stop processing if it's running.
        """
        if self.logic:
            self.logic.stop()
        self.status.emit("Stop signal sent to logic.")
