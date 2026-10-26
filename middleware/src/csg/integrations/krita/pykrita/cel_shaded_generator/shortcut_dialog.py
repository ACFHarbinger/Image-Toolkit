"""Explicit shortcut editor; shortcuts remain unassigned until the artist opts in."""

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit


class ShortcutDialog(QDialog):
    def __init__(self, shortcuts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Tutor Shortcuts")
        self._fields = {action: QLineEdit(shortcuts.get(action, ""), self) for action in shortcuts}
        self._error = QLabel("Leave a field empty to keep that action unassigned.", self)
        self._error.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout = QFormLayout(self)
        for action, field in self._fields.items():
            layout.addRow(action.title(), field)
        layout.addRow(self._error)
        layout.addRow(buttons)

    def shortcuts(self):
        return {action: field.text().strip() for action, field in self._fields.items()}

    def _accept_if_valid(self):
        shortcuts = self.shortcuts()
        values = [value for value in shortcuts.values() if value]
        if any(QKeySequence(value).isEmpty() for value in values):
            self._error.setText("One or more shortcut sequences are invalid.")
            return
        if len({value.casefold() for value in values}) != len(values):
            self._error.setText("Review, Accept, and Reject must use different shortcuts.")
            return
        self.accept()
