import os
from PySide6.QtCore import Qt, QObject, Slot, Property, Signal, QUrl
from PySide6.QtQml import QQmlApplicationEngine


class LogWindow(QObject):
    """A dedicated window to display the synchronization log using QML."""
    
    log_changed = Signal()

    def __init__(self, tab_name="Drive Sync", parent=None):
        super().__init__(parent)
        self._log_text = "[INFO] Log initialized.\n"
        self._tab_name = tab_name
        
        # QML Setup
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("backend", self)
        
        qml_path = os.path.join(os.path.dirname(__file__), "..", "..", "qml", "windows", "LogWindow.qml")
        self.engine.load(QUrl.fromLocalFile(os.path.abspath(qml_path)))
        
        if not self.engine.rootObjects():
            print(f"Error: Could not load LogWindow.qml for {tab_name}")
            return
            
        self.root = self.engine.rootObjects()[0]
        self.root.setTitle(f"{tab_name} Status Log")

    @Property(str, notify=log_changed)
    def logText(self):
        return self._log_text

    @Slot(str)
    def append_log(self, text: str):
        """Method to safely append text to the log."""
        self._log_text += text + "\n"
        self.log_changed.emit()

    @Slot()
    def clear_log(self):
        """Method to clear the log content."""
        self._log_text = ""
        self.log_changed.emit()

    @Slot()
    def save_logs_to_file(self):
        """Dummy slot for saving logs (to be implemented if needed)"""
        print("Save logs to file requested")

    def show(self):
        if hasattr(self, 'root'):
            self.root.show()

    def hide(self):
        if hasattr(self, 'root'):
            self.root.hide()

    def isVisible(self):
        return hasattr(self, 'root') and self.root.isVisible()

    def activateWindow(self):
        if hasattr(self, 'root'):
            self.root.raise_()
            self.root.requestActivate()
