"""Video-directory import dialog for series listings."""

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

from gui.src.constants.listings import ENTRY_STATUS, ENTRY_TYPES, VIDEO_IMPORT_EXTS
from gui.src.elements.database.common.listings_common import (
    _parse_video_series,
    _persist_splitter,
    _scan_video_directory,
)
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
from .profile import SERIES_PROFILE


class _DirectoryImportDialog(BaseDirectoryImportDialog):
    """Pick a video directory, review detected series, configure metadata, import."""

    def __init__(self, existing_titles: set[str], parent=None):
        self._profile = SERIES_PROFILE
        super().__init__(self._profile.window_title, parent)
        self._existing_titles = existing_titles
        self._scan_result: dict = {}

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
            ["", "Series Name", "Episodes", "Status"],
            stretch_columns=(1,),
        )
        self._table.setColumnWidth(2, 72)
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
        self._f_type.addItems(ENTRY_TYPES)
        self._f_type.setCurrentText("Anime")
        self._f_status = QComboBox()
        self._f_status.addItems(ENTRY_STATUS)
        self._f_status.setCurrentText("Plan to Watch")
        self._f_year = QSpinBox()
        self._f_year.setRange(0, 2100)
        self._f_year.setValue(0)
        self._f_year.setSpecialValueText("Unknown")
        self._f_genres = QLineEdit()
        self._f_genres.setPlaceholderText("e.g. Action, Comedy")
        self._f_tags = QLineEdit()
        self._f_tags.setPlaceholderText("e.g. subbed, seasonal")
        self._f_creator = QLineEdit()
        self._f_creator.setPlaceholderText("Studio / Author (optional)")

        meta_form.addRow("Type:", self._f_type)
        meta_form.addRow("Status:", self._f_status)
        meta_form.addRow("Year:", self._f_year)
        meta_form.addRow("Genres:", self._f_genres)
        meta_form.addRow("Tags:", self._f_tags)
        meta_form.addRow("Creator:", self._f_creator)
        right_vbox.addWidget(meta_group)
        right_vbox.addStretch()

        info_lbl = QLabel(
            "<small>"
            "<b>What gets created per series:</b><br>"
            "• Title from the filename prefix before <code> - </code><br>"
            "• <i>Episodes</i> count = number of matching files<br>"
            "• <i>Local File</i> = path to the first episode<br>"
            "• Individual episode entries, each with its own file path<br>"
            "• Episode number extracted from the filename<br><br>"
            "<b>Filename format expected:</b><br>"
            "<code>&lt;Series&gt; - &lt;##&gt; [suffix].ext</code>"
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
        self._scan_result = _scan_video_directory(directory)
        self._populate_table()

    def _do_subdirectory_scan(self):
        directory = self._dir_edit.text().strip() or self._directory
        if not directory or not Path(directory).is_dir():
            QMessageBox.warning(
                self, "Invalid Directory", "Please select a valid directory first."
            )
            return
        self._directory = directory
        self._scan_result = {}
        p = Path(directory)
        pattern = re.compile(r"^[^\W_]+(?:_[^\W_]+)*$", re.UNICODE)

        from gui.src.windows.settings.app_settings import AppSettings

        recursive = AppSettings.recursive_scan()

        try:
            for child in p.iterdir():
                if child.is_dir() and pattern.match(child.name):
                    series_name = " ".join(child.name.split("_"))
                    episodes = []
                    try:
                        if recursive:
                            entries = sorted(child.rglob("*"), key=lambda e: e.name.lower())
                        else:
                            entries = sorted(child.iterdir(), key=lambda e: e.name.lower())
                    except OSError:
                        continue

                    for entry in entries:
                        if not entry.is_file():
                            continue
                        if entry.suffix.lower() not in VIDEO_IMPORT_EXTS:
                            continue
                        if " - " in entry.name:
                            _, ep_num = _parse_video_series(entry.name)
                        else:
                            m = re.search(r"(\d+)", entry.name)
                            ep_num = int(m.group(1)) if m else None
                        episodes.append((ep_num, str(entry.absolute())))

                    if episodes:
                        episodes.sort(key=lambda x: (x[0] is None, x[0] or 0))
                        self._scan_result[series_name] = episodes
        except Exception as e:
            QMessageBox.critical(self, "Scan Error", f"Failed to scan directory: {e}")
            return

        self._populate_table()

    def _populate_table(self):
        self._table.setRowCount(0)
        new_count = exists_count = 0

        for series_name, episodes in sorted(
            self._scan_result.items(), key=lambda kv: kv[0].lower()
        ):
            already = series_name.lower() in self._existing_titles
            if already:
                exists_count += 1
            else:
                new_count += 1

            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setCellWidget(row, 0, make_checkbox_cell(not already))

            name_item = QTableWidgetItem(series_name)
            name_item.setData(Qt.ItemDataRole.UserRole, series_name)
            name_item.setToolTip(series_name)
            self._table.setItem(row, 1, name_item)

            ep_item = QTableWidgetItem(str(len(episodes)))
            ep_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, ep_item)
            self._table.setItem(row, 3, make_status_item(already))

        total = len(self._scan_result)
        self._status_lbl.setText(
            f"Found {total} series — {new_count} new, {exists_count} already in "
            f"{self._profile.import_noun}."
        )
        self._import_btn.setEnabled(total > 0)

    def get_selected_series(self) -> list[str]:
        from PySide6.QtWidgets import QCheckBox

        selected = []
        for row in range(self._table.rowCount()):
            cw = self._table.cellWidget(row, 0)
            if cw:
                chk = cw.findChild(QCheckBox)
                if chk and chk.isChecked():
                    item = self._table.item(row, 1)
                    if item:
                        selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected

    def get_scan_result(self) -> dict:
        return self._scan_result

    def get_metadata(self) -> dict:
        return {
            "type": self._f_type.currentText(),
            "status": self._f_status.currentText(),
            "year": self._f_year.value(),
            "genres": self._f_genres.text().strip(),
            "tags": self._f_tags.text().strip(),
            "creator": self._f_creator.text().strip(),
        }


__all__ = ["_DirectoryImportDialog"]
