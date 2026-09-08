"""Image-directory import dialog for entity listings."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.src.constants.listings import ENTITY_ROLES, ENTITY_TYPES
from gui.src.elements.database.common.listings_common import _persist_splitter
from gui.src.elements.database.dialog.common.base_directory_import_dialog import (
    BaseDirectoryImportDialog,
)
from gui.src.theming.theme_api import qss

from ._shared import (
    build_confirm_button_row,
    build_selection_button_row,
    make_checkbox_cell,
    make_results_table,
    make_status_item,
)
from .profile import ENTITY_PROFILE


class _EntityDirectoryImportDialog(BaseDirectoryImportDialog):
    """Pick an image directory, review detected entities, configure metadata, import."""

    def __init__(self, existing_names: set[str], parent=None):
        self._profile = ENTITY_PROFILE
        super().__init__(self._profile.window_title, parent)
        self._existing_names = existing_names
        self._scan_result: list = []

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        dir_group = QGroupBox(self._profile.directory_group_title)
        dir_row = QHBoxLayout(dir_group)
        dir_row.setSpacing(6)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText(self._profile.directory_placeholder)
        self._dir_edit.setReadOnly(True)
        browse_btn = QPushButton("📁 Browse…")
        browse_btn.setFixedWidth(100)
        browse_btn.clicked.connect(self._browse)
        scan_btn = QPushButton("🔍 Scan")
        scan_btn.setFixedWidth(80)
        scan_btn.clicked.connect(self._do_subdirectory_scan)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(browse_btn)
        dir_row.addWidget(scan_btn)
        root.addWidget(dir_group)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_vbox = QVBoxLayout(left)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(6)

        self._status_lbl = QLabel(self._profile.status_idle_text)
        self._status_lbl.setStyleSheet(qss("directory_import_status_label"))
        left_vbox.addWidget(self._status_lbl)

        self._table = make_results_table(
            ["", "Detected Name", "Filename", "Status"],
            stretch_columns=(1, 2),
        )
        left_vbox.addWidget(self._table, 1)
        left_vbox.addLayout(
            build_selection_button_row(self._select_all_new, self._deselect_all)
        )
        splitter.addWidget(left)

        right = QWidget()
        right_vbox = QVBoxLayout(right)
        right_vbox.setContentsMargins(6, 0, 0, 0)
        right_vbox.setSpacing(8)

        meta_group = QGroupBox(self._profile.metadata_group_title)
        meta_form = QFormLayout(meta_group)
        meta_form.setSpacing(8)

        self._f_type = QComboBox()
        self._f_type.addItems(ENTITY_TYPES)
        self._f_type.setCurrentText("Person")
        self._f_role = QComboBox()
        self._f_role.addItems(ENTITY_ROLES)
        self._f_role.setCurrentText("Director")
        self._f_rating = QSpinBox()
        self._f_rating.setRange(0, 10)
        self._f_rating.setValue(0)
        self._f_year = QSpinBox()
        self._f_year.setRange(0, 2100)
        self._f_year.setValue(0)
        self._f_year.setSpecialValueText("Unknown")

        meta_form.addRow("Type:", self._f_type)
        meta_form.addRow("Role:", self._f_role)
        meta_form.addRow("Rating:", self._f_rating)
        meta_form.addRow("Active Year:", self._f_year)
        right_vbox.addWidget(meta_group)
        right_vbox.addStretch()

        info_lbl = QLabel(
            "<small>"
            "<b>Filename format expected:</b><br>"
            "<code>&lt;First Name&gt; &lt;Last Name&gt;&lt;Optional Number&gt;.ext</code><br><br>"
            "<b>What gets created:</b><br>"
            "• First name and last name parsed from the image filename<br>"
            "• Optional trailing digits are stripped from the entity name<br>"
            "• Image copied and associated automatically as entity profile picture"
            "</small>"
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet(qss("directory_import_info_label"))
        right_vbox.addWidget(info_lbl)
        splitter.addWidget(right)

        splitter.setSizes([520, 300])
        _persist_splitter(splitter, self._profile.splitter_key)
        root.addWidget(splitter, 1)

        self._import_btn = QPushButton("📥 Import Selected")
        self._import_btn.clicked.connect(self.accept)
        root.addLayout(build_confirm_button_row(self._import_btn, self.reject))

    def _browse(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            self._profile.browse_dialog_title,
            self._directory or str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
            | QFileDialog.Option.DontResolveSymlinks
            | QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            self._directory = directory
            self._dir_edit.setText(directory)
            self._do_filename_scan()

    def _do_filename_scan(self):
        directory = self._dir_edit.text().strip() or self._directory
        if not directory or not Path(directory).is_dir():
            QMessageBox.warning(
                self, "Invalid Directory", "Please select a valid directory first."
            )
            return
        self._directory = directory

        self._scan_result = []
        p = Path(directory)
        valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        try:
            for item in p.iterdir():
                if item.is_file() and item.suffix.lower() in valid_exts:
                    stem = item.stem
                    clean_stem = re.sub(r"\s*\d+$", "", stem).strip()
                    parts = clean_stem.split()
                    if not parts:
                        continue
                    first_name = parts[0]
                    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                    self._scan_result.append(
                        (first_name, last_name, str(item.absolute()))
                    )
        except Exception as e:
            QMessageBox.critical(self, "Scan Error", f"Failed to scan directory: {e}")
            return

        self._populate_table()

    def _do_subdirectory_scan(self):
        directory = self._dir_edit.text().strip() or self._directory
        if not directory or not Path(directory).is_dir():
            QMessageBox.warning(
                self, "Invalid Directory", "Please select a valid directory first."
            )
            return
        self._directory = directory

        self._scan_result = []
        p = Path(directory)
        valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        pattern = re.compile(r"^[^\W_]+(?:_[^\W_]+)*$", re.UNICODE)
        try:
            for child in p.iterdir():
                if child.is_dir() and pattern.match(child.name):
                    parts = child.name.split("_")
                    first_name = parts[0]
                    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                    image_path = ""
                    for f in child.iterdir():
                        if f.is_file() and f.suffix.lower() in valid_exts:
                            image_path = str(f.absolute())
                            break
                    self._scan_result.append((first_name, last_name, image_path))
        except Exception as e:
            QMessageBox.critical(self, "Scan Error", f"Failed to scan directory: {e}")
            return

        self._populate_table()

    def _populate_table(self):
        self._table.setRowCount(0)
        new_count = exists_count = 0
        sorted_rows = sorted(
            self._scan_result, key=lambda x: f"{x[0]} {x[1]}".lower()
        )
        for first_name, last_name, file_path in sorted_rows:
            full_name = f"{first_name} {last_name}".strip()
            already = full_name.lower() in self._existing_names
            if already:
                exists_count += 1
            else:
                new_count += 1

            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setCellWidget(row, 0, make_checkbox_cell(not already))
            self._table.setItem(row, 1, QTableWidgetItem(full_name))
            file_item = QTableWidgetItem(Path(file_path).name)
            file_item.setToolTip(file_path)
            self._table.setItem(row, 2, file_item)
            self._table.setItem(row, 3, make_status_item(already))

        total = len(self._scan_result)
        self._status_lbl.setText(
            f"Found {total} images — {new_count} new, {exists_count} already in "
            f"{self._profile.import_noun}."
        )
        self._import_btn.setEnabled(total > 0)

    def get_selected_entities(self) -> list[tuple[str, str, str]]:
        from PySide6.QtWidgets import QCheckBox

        selected = []
        sorted_rows = sorted(
            self._scan_result, key=lambda x: f"{x[0]} {x[1]}".lower()
        )
        for row in range(self._table.rowCount()):
            cw = self._table.cellWidget(row, 0)
            if cw:
                chk = cw.findChild(QCheckBox)
                if chk and chk.isChecked():
                    selected.append(sorted_rows[row])
        return selected

    def get_metadata(self) -> dict:
        return {
            "type": self._f_type.currentText(),
            "role": self._f_role.currentText(),
            "rating": self._f_rating.value(),
            "year": self._f_year.value(),
        }


__all__ = ["_EntityDirectoryImportDialog"]
