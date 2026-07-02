import re
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

from gui.src.constants.listings import ENTITY_TYPES, ENTITY_ROLES
from gui.src.styles.style import SHARED_BUTTON_STYLE
from gui.src.tabs.core.elements.common.listings_common import _persist_splitter
from gui.src.tabs.core.elements.dialog.common.base_directory_import_dialog import (
    BaseDirectoryImportDialog,
)


class _EntityDirectoryImportDialog(BaseDirectoryImportDialog):
    """One-shot wizard: pick a directory of entity images → review detected
    entities → configure shared metadata → confirm or cancel import."""

    def __init__(self, existing_names: "set[str]", parent=None):
        super().__init__("📂 Import Entities from Image Directory", parent)
        self._existing_names = existing_names  # lowercase normalised set
        self._scan_result: list = []  # list of tuples: (first_name, last_name, file_path)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # ── Directory picker row ──────────────────────────────────────
        dir_group = QGroupBox("Image Directory")
        dir_row = QHBoxLayout(dir_group)
        dir_row.setSpacing(6)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText(
            "Select the folder that contains your entity image files…"
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

        # Left — detected-entities table
        left = QWidget()
        left_vbox = QVBoxLayout(left)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(6)

        self._status_lbl = QLabel("Scan a directory to detect entity images.")
        self._status_lbl.setStyleSheet("color:#888; font-size:11px;")
        left_vbox.addWidget(self._status_lbl)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["", "Detected Name", "Filename", "Status"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._table.setColumnWidth(0, 32)
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

        meta_group = QGroupBox("Metadata Applied to All New Entities")
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
        info_lbl.setStyleSheet("color:#888; font-size:10px; border:none;")
        right_vbox.addWidget(info_lbl)
        splitter.addWidget(right)

        splitter.setSizes([520, 300])
        _persist_splitter(splitter, "entity_directory_import_dialog")
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
            "Select Entity Image Directory",
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

        # Scan for images
        self._scan_result = []
        p = Path(directory)
        valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

        try:
            for item in p.iterdir():
                if item.is_file() and item.suffix.lower() in valid_exts:
                    stem = item.stem
                    # remove optional trailing number and spaces
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

    def _populate_table(self):
        self._table.setRowCount(0)
        new_count = exists_count = 0

        for first_name, last_name, file_path in sorted(
            self._scan_result, key=lambda x: f"{x[0]} {x[1]}".lower()
        ):
            full_name = f"{first_name} {last_name}".strip()
            already = full_name.lower() in self._existing_names
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

            # Col 1 – Detected Name
            name_item = QTableWidgetItem(full_name)
            self._table.setItem(row, 1, name_item)

            # Col 2 – Filename
            file_item = QTableWidgetItem(Path(file_path).name)
            file_item.setToolTip(file_path)
            self._table.setItem(row, 2, file_item)

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
            f"Found {total} images — {new_count} new, {exists_count} already in entities."
        )
        self._import_btn.setEnabled(total > 0)

    def get_selected_entities(self) -> "list[tuple[str, str, str]]":
        """Return the list of (first_name, last_name, file_path) whose checkboxes are ticked."""
        selected = []
        for row in range(self._table.rowCount()):
            cw = self._table.cellWidget(row, 0)
            if cw:
                chk = cw.findChild(QCheckBox)
                if chk and chk.isChecked():
                    first_name, last_name, file_path = sorted(
                        self._scan_result, key=lambda x: f"{x[0]} {x[1]}".lower()
                    )[row]
                    selected.append((first_name, last_name, file_path))
        return selected

    def get_metadata(self) -> dict:
        return {
            "type": self._f_type.currentText(),
            "role": self._f_role.currentText(),
            "rating": self._f_rating.value(),
            "year": self._f_year.value(),
        }
