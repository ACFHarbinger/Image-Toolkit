from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit


class LogWindow(QWidget):
    """A dedicated window to display the synchronization log."""

    def __init__(self, tab_name="Drive Sync", parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle(f"{tab_name} Status Log")
        self.setGeometry(100, 100, 700, 500)

        main_layout = QVBoxLayout(self)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet(
            "background:#1e1e1e; color:#b9bbbe; border:none; font-family: monospace;"
        )

        main_layout.addWidget(self.log_output)

    def append_log(self, text: str):
        """Method to safely append text to the log."""
        self.log_output.append(text)

    def clear_log(self):
        """Method to clear the log content."""
        self.log_output.clear()

    def closeEvent(self, event):
        """Ensure the window hides instead of closing completely."""
        self.hide()
        event.ignore()
