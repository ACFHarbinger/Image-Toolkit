from gui.src.constants import LEVEL_COLORS
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LogWindow(QWidget):
    """Upgraded log window — colour-coded levels, copy/save, auto-scroll toggle.

    GUI/UX §2.17D: QPlainTextEdit, ANSI-style level colours, Copy All / Save /
    Clear buttons, Follow toggle (auto-scroll to bottom on new entries).
    """

    def __init__(self, tab_name: str = "Log", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(f"{tab_name} — Log")
        self.setMinimumSize(720, 420)
        self.setStyleSheet("background:#1e1e1e; color:#cccccc;")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Log output
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Monospace", 9))
        self.log_output.setStyleSheet(
            "QPlainTextEdit{background:#1e1e1e;color:#cccccc;"
            "border:1px solid #2c2f33;border-radius:4px;}"
        )
        root.addWidget(self.log_output, 1)

        # Toolbar
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self._follow_chk = QCheckBox("Follow")
        self._follow_chk.setChecked(True)
        self._follow_chk.setToolTip("Auto-scroll to newest log entry")
        bar.addWidget(self._follow_chk)
        bar.addStretch()

        for label, slot in (
            ("Copy All", self._copy_all),
            ("Save…", self._save_to_file),
            ("Clear", self._clear),
        ):
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setStyleSheet(
                "QPushButton{background:#2c2f33;color:#cccccc;border:1px solid #4f545c;"
                "border-radius:4px;padding:0 10px;}"
                "QPushButton:hover{background:#4f545c;}"
            )
            btn.clicked.connect(slot)
            bar.addWidget(btn)

        root.addLayout(bar)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def append_log(self, text: str, level: str = "INFO") -> None:
        """Append *text* with a colour matched to *level*."""
        colour = LEVEL_COLORS.get(level.upper(), LEVEL_COLORS["INFO"])
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        line = f"[{timestamp}] {text}"

        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(colour))
        cursor.insertText(line + "\n", fmt)

        if self._follow_chk.isChecked():
            self.log_output.setTextCursor(cursor)
            self.log_output.ensureCursorVisible()

    def clear_log(self) -> None:
        self.log_output.clear()

    # ------------------------------------------------------------------
    # Toolbar slots
    # ------------------------------------------------------------------
    def _copy_all(self) -> None:
        QGuiApplication.clipboard().setText(self.log_output.toPlainText())

    def _save_to_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Log", "", "Text files (*.txt);;All files (*.*)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(self.log_output.toPlainText())
            except OSError as exc:
                self.append_log(f"Failed to save log: {exc}", "ERROR")

    def _clear(self) -> None:
        self.log_output.clear()

    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self.hide()
        event.ignore()
