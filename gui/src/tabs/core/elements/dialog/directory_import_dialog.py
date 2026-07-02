from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QComboBox,
    QSplitter,
    QWidget,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)

from gui.src.constants.listings import ENTRY_TYPES, ENTRY_STATUS
from gui.src.styles.style import SHARED_BUTTON_STYLE
from gui.src.tabs.core.elements.common.listings_common import (
    _persist_splitter,
    _scan_video_directory,
)
from gui.src.tabs.core.elements.dialog.common.base_directory_import_dialog import (
    BaseDirectoryImportDialog,
)


class _DirectoryImportDialog(BaseDirectoryImportDialog):
    """One-shot wizard: pick a directory of video files → review detected
    series → configure shared metadata → confirm or cancel import."""

    def __init__(self, existing_titles: "set[str]", parent=None):
        super().__init__("📂 Import Listings from Video Directory", parent)
        self._existing_titles = existing_titles  # lowercase normalised set
        self._scan_result: dict = {}  # {series_name: [(ep_num, path), ...]}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # ── Directory picker row ──────────────────────────────────────
        dir_group = QGroupBox("Video Directory")
        dir_row = QHBoxLayout(dir_group)
        dir_row.setSpacing(6)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText(
            "Select the folder that contains your video files…"
        )
        self._dir_edit.setReadOnly(True)
        browse_btn = QPushButton("📁 Browse…")
        browse_btn.setFixedWidth(100)
        browse_btn.clicked.connect(self._browse)
        scan_btn = QPushButton("🔍 Scan")
        scan_btn.setFixedWidth(80)
        scan_btn.clicked.connect(self._do_scan)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(browse_btn)
        dir_row.addWidget(scan_btn)
        root.addWidget(dir_group)

        # ── Middle: table left | options right ────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left — detected-series table
        left = QWidget()
        left_vbox = QVBoxLayout(left)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(6)

        self._status_lbl = QLabel("Scan a directory to detect series.")
        self._status_lbl.setStyleSheet("color:#888; font-size:11px;")
        left_vbox.addWidget(self._status_lbl)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["", "Series Name", "Episodes", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.setColumnWidth(0, 32)
        self._table.setColumnWidth(2, 72)
        self._table.setColumnWidth(3, 120)
        self._table.verticalHeader().hide()
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget { background:#23272a; alternate-background-color:#252830;"
            "  border:1px solid #4f545c; border-radius:6px; gridline-color:#3a3d42; }"
            "QTableWidget::item { color:white; padding:3px; }"
            "QTableWidget::item:selected { background:#00bcd4; color:black; }"
            "QHeaderView::section { background:#2c2f33; color:#888; border:none; padding:4px; }"
        )
        left_vbox.addWidget(self._table, 1)

        sel_row = QHBoxLayout()
        sel_all_btn = QPushButton("☑ Select All New")
        sel_all_btn.setFixedHeight(36)
        sel_all_btn.setStyleSheet("padding: 6px 12px;")
        sel_all_btn.clicked.connect(self._select_all_new)
        sel_none_btn = QPushButton("☐ Deselect All")
        sel_none_btn.setFixedHeight(36)
        sel_none_btn.setStyleSheet("padding: 6px 12px;")
        sel_none_btn.clicked.connect(self._deselect_all)
        sel_row.addWidget(sel_all_btn)
        sel_row.addWidget(sel_none_btn)
        sel_row.addStretch()
        left_vbox.addLayout(sel_row)
        splitter.addWidget(left)

        # Right — metadata options
        right = QWidget()
        right_vbox = QVBoxLayout(right)
        right_vbox.setContentsMargins(6, 0, 0, 0)
        right_vbox.setSpacing(8)

        meta_group = QGroupBox("Metadata Applied to All New Entries")
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
        info_lbl.setStyleSheet("color:#888; font-size:10px; border:none;")
        right_vbox.addWidget(info_lbl)
        splitter.addWidget(right)

        splitter.setSizes([520, 300])
        _persist_splitter(splitter, "directory_import_dialog")
        root.addWidget(splitter, 1)

        # ── Confirm / cancel ──────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(90)
        cancel_btn.clicked.connect(self.reject)
        self._import_btn = QPushButton("📥 Import Selected")
        self._import_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        self._import_btn.setFixedWidth(150)
        self._import_btn.setEnabled(False)
        self._import_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._import_btn)
        root.addLayout(btn_row)

    def _browse(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Video Directory",
            self._directory or str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
            | QFileDialog.Option.DontResolveSymlinks
            | QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            self._directory = directory
            self._dir_edit.setText(directory)
            self._do_scan()

    def _do_scan(self):
        directory = self._dir_edit.text().strip() or self._directory
        if not directory or not Path(directory).is_dir():
            QMessageBox.warning(
                self, "Invalid Directory", "Please select a valid directory first."
            )
            return
        self._directory = directory
        self._scan_result = _scan_video_directory(directory)
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

            # Col 0 – checkbox (wrapped in a centred container)
            chk = QCheckBox()
            chk.setChecked(not already)
            chk.setStyleSheet("QCheckBox { margin-left:6px; }")
            container = QWidget()
            c_lay = QHBoxLayout(container)
            c_lay.addWidget(chk)
            c_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_lay.setContentsMargins(0, 0, 0, 0)
            self._table.setCellWidget(row, 0, container)

            # Col 1 – series name (store original as UserRole for retrieval)
            name_item = QTableWidgetItem(series_name)
            name_item.setData(Qt.ItemDataRole.UserRole, series_name)
            name_item.setToolTip(series_name)
            self._table.setItem(row, 1, name_item)

            # Col 2 – episode count
            ep_item = QTableWidgetItem(str(len(episodes)))
            ep_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, ep_item)

            # Col 3 – new / already-exists badge
            if already:
                st_item = QTableWidgetItem("⚠ Already exists")
                st_item.setForeground(QColor("#f39c12"))
            else:
                st_item = QTableWidgetItem("✓ New")
                st_item.setForeground(QColor("#2ecc71"))
            self._table.setItem(row, 3, st_item)

        total = len(self._scan_result)
        self._status_lbl.setText(
            f"Found {total} series — {new_count} new, {exists_count} already in listings."
        )
        self._import_btn.setEnabled(total > 0)

    def get_selected_series(self) -> "list[str]":
        """Return the list of series names whose checkboxes are ticked."""
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
