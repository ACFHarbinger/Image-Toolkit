from PySide6.QtCore import QObject, Signal, Property, Slot

class LogBackend(QObject):
    log_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._log_text = ""

    @Property(str, notify=log_changed)
    def logText(self):
        return self._log_text

    @Slot()
    def clear_log(self):
        self._log_text = ""
        self.log_changed.emit()

    @Slot(str)
    def append_log(self, msg):
        self._log_text += msg + "\n"
        self.log_changed.emit()

    @Slot()
    def save_logs_to_file(self):
        # Placeholder or implement file saving
        print("Saving logs to file (not implemented)")
