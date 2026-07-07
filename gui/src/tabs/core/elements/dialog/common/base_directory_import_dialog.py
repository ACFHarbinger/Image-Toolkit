from PySide6.QtWidgets import QCheckBox, QDialog, QFileDialog


class BaseDirectoryImportDialog(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(840, 620)
        self.setStyleSheet(
            "QDialog { background:#2c2f33; color:white; }"
            "QLabel  { color:white; }"
            "QLineEdit, QSpinBox, QComboBox { background:#23272a; color:white;"
            "  border:1px solid #4f545c; border-radius:4px; padding:4px; }"
            "QGroupBox { border:1px solid #4f545c; border-radius:6px;"
            "  margin-top:8px; color:#00bcd4; font-weight:bold; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }"
        )
        self._directory = ""
        self._dir_edit = None  # To be assigned in subclass
        self._table = None  # To be assigned in subclass

    def _browse(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Directory", self._directory
        )
        if dir_path:
            self._directory = dir_path
            if self._dir_edit:
                self._dir_edit.setText(dir_path)

    def _select_all_new(self):
        if not self._table:
            return
        for r in range(self._table.rowCount()):
            status_item = self._table.item(r, 3)
            if status_item and "New" in status_item.text():
                self._set_row_check(r, True)

    def _deselect_all(self):
        if not self._table:
            return
        for r in range(self._table.rowCount()):
            self._set_row_check(r, False)

    def _set_row_check(self, row: int, state: bool):
        if not self._table:
            return
        widget = self._table.cellWidget(row, 0)
        if isinstance(widget, QCheckBox):
            widget.setChecked(state)
        elif widget:
            chk = widget.findChild(QCheckBox)
            if chk:
                chk.setChecked(state)

