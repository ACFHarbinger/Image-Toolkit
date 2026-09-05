"""
Contact Sheet Generator Dialog (GUI/UX §2.19B).

Interactive modal dialog allowing users to customize contact sheet layout,
thumbnail size, columns, labels, background color, and export to PNG / PDF.
"""

from __future__ import annotations

import os
from typing import Optional, Sequence

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...utils.contact_sheet_generator import generate_contact_sheet


class _ContactSheetWorker(QThread):
    """Background worker to composite large contact sheets without UI freezes."""

    finished = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        image_paths: Sequence[str],
        columns: int,
        thumb_size: tuple[int, int],
        padding: int,
        margin: int,
        bg_color: tuple[int, int, int],
        show_labels: bool,
        output_path: str,
    ) -> None:
        super().__init__()
        self.image_paths = image_paths
        self.columns = columns
        self.thumb_size = thumb_size
        self.padding = padding
        self.margin = margin
        self.bg_color = bg_color
        self.show_labels = show_labels
        self.output_path = output_path

    def run(self) -> None:
        try:
            generate_contact_sheet(
                image_paths=self.image_paths,
                columns=self.columns,
                thumb_size=self.thumb_size,
                padding=self.padding,
                margin=self.margin,
                bg_color=self.bg_color,
                show_labels=self.show_labels,
                output_path=self.output_path,
            )
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))


class ContactSheetDialog(QDialog):
    """Configuration and export dialog for generating contact sheets."""

    def __init__(self, image_paths: Sequence[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.image_paths = [p for p in image_paths if os.path.isfile(p)]
        self._bg_rgb: tuple[int, int, int] = (30, 30, 30)
        self._worker: Optional[_ContactSheetWorker] = None

        self.setWindowTitle("Generate Contact Sheet")
        self.resize(480, 420)
        self.setMinimumSize(420, 360)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Info
        header = QLabel(f"<b>Contact Sheet Generator</b><br><span style='color: #888;'>Exporting {len(self.image_paths)} image(s) as a tiled proof sheet</span>")
        layout.addWidget(header)

        # Settings Group
        group = QGroupBox("Layout & Appearance Settings")
        form = QFormLayout(group)
        form.setSpacing(10)

        # Columns
        self.spin_columns = QSpinBox()
        self.spin_columns.setRange(1, 16)
        self.spin_columns.setValue(min(4, max(1, len(self.image_paths))))
        form.addRow("Columns:", self.spin_columns)

        # Thumbnail Size
        self.combo_size = QComboBox()
        self.combo_size.addItems(["Small (128 × 128 px)", "Medium (256 × 256 px)", "Large (384 × 384 px)", "Extra Large (512 × 512 px)"])
        self.combo_size.setCurrentIndex(1)
        form.addRow("Thumbnail Size:", self.combo_size)

        # Padding & Margins
        spacing_layout = QHBoxLayout()
        self.spin_padding = QSpinBox()
        self.spin_padding.setRange(0, 64)
        self.spin_padding.setValue(12)
        spacing_layout.addWidget(QLabel("Padding:"))
        spacing_layout.addWidget(self.spin_padding)

        self.spin_margin = QSpinBox()
        self.spin_margin.setRange(0, 128)
        self.spin_margin.setValue(24)
        spacing_layout.addWidget(QLabel("Margin:"))
        spacing_layout.addWidget(self.spin_margin)
        form.addRow("Spacing (px):", spacing_layout)

        # Labels
        self.chk_labels = QCheckBox("Show filename labels below thumbnails")
        self.chk_labels.setChecked(True)
        form.addRow("", self.chk_labels)

        # Background color
        bg_layout = QHBoxLayout()
        self.btn_bg_color = QPushButton("⬛ Dark (#1E1E1E)")
        self.btn_bg_color.clicked.connect(self._pick_bg_color)
        bg_layout.addWidget(self.btn_bg_color)
        form.addRow("Background Color:", bg_layout)

        layout.addWidget(group)

        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_generate = QPushButton("Generate & Save…")
        self.btn_generate.setDefault(True)
        self.btn_generate.clicked.connect(self._start_export)
        btn_layout.addWidget(self.btn_generate)

        layout.addLayout(btn_layout)

    def _pick_bg_color(self) -> None:
        col = QColorDialog.getColor(parent=self, title="Select Background Color")
        if col.isValid():
            self._bg_rgb = (col.red(), col.green(), col.blue())
            hex_str = col.name().upper()
            self.btn_bg_color.setText(f"🎨 Custom ({hex_str})")

    def _get_thumb_size(self) -> tuple[int, int]:
        idx = self.combo_size.currentIndex()
        sizes = [(128, 128), (256, 256), (384, 384), (512, 512)]
        return sizes[idx] if 0 <= idx < len(sizes) else (256, 256)

    def _start_export(self) -> None:
        if not self.image_paths:
            QMessageBox.warning(self, "No Images", "No valid images to generate contact sheet.")
            return

        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Save Contact Sheet",
            "contact_sheet.png",
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;PDF Document (*.pdf)",
        )
        if not dest:
            return

        self.btn_generate.setEnabled(False)
        self.progress_bar.setVisible(True)

        self._worker = _ContactSheetWorker(
            image_paths=self.image_paths,
            columns=self.spin_columns.value(),
            thumb_size=self._get_thumb_size(),
            padding=self.spin_padding.value(),
            margin=self.spin_margin.value(),
            bg_color=self._bg_rgb,
            show_labels=self.chk_labels.isChecked(),
            output_path=dest,
        )
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, out_path: str) -> None:
        self.progress_bar.setVisible(False)
        self.btn_generate.setEnabled(True)
        try:
            from ...windows.main._notify import show_toast_notification
            show_toast_notification(f"Contact sheet saved: {Path(out_path).name}", "success")
        except Exception:
            pass
        QMessageBox.information(
            self,
            "Contact Sheet Created",
            f"Contact sheet successfully saved to:\n{out_path}",
        )
        self.accept()

    def _on_error(self, err: str) -> None:
        self.progress_bar.setVisible(False)
        self.btn_generate.setEnabled(True)
        QMessageBox.critical(self, "Export Error", f"Failed to generate contact sheet:\n{err}")


__all__ = ["ContactSheetDialog"]
