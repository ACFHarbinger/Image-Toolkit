from backend.src.web import WebRequestsLogic
from PySide6.QtCore import Signal

from gui.src.helpers.base import BaseQThreadWorker
from gui.src.qt_event_bridge import QtEventBridge


class WebRequestsWorker(BaseQThreadWorker):
    status = Signal(str)  # status message
    finished = Signal(object)  # result message str, None on failure/cancel

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.logic = None
        # Bridges are QObjects: construct here on the GUI thread, attach in
        # _execute() once the logic object exists (issue #529).
        self._status_bridge = QtEventBridge(self.status.emit, parent=self)
        self._error_bridge = QtEventBridge(self._on_logic_error, parent=self)
        self._finished_bridge = QtEventBridge(self._on_logic_finished, parent=self)
        self._result_message: object = None

    def _on_logic_error(self, message: str) -> None:
        self.error.emit(RuntimeError(message))

    def _on_logic_finished(self, message: str) -> None:
        self._result_message = message

    def _execute(self) -> object:
        self.logic = WebRequestsLogic(self.config)

        # Bridge backend Observables onto the GUI thread (issue #529).
        self._status_bridge.attach(self.logic.on_status)
        self._error_bridge.attach(self.logic.on_error)
        self._finished_bridge.attach(self.logic.on_finished)
        try:
            self.status.emit("Starting requests...")

            # Run the main logic
            self.logic.run()
            return self._result_message

        finally:
            self._status_bridge.detach()
            self._error_bridge.detach()
            self._finished_bridge.detach()

    def stop(self):
        """
        Signals the logic class to stop processing if it's running.
        """
        if self.logic:
            self.logic.stop()
        self.status.emit("Stop signal sent to logic.")
        self.requestInterruption()
