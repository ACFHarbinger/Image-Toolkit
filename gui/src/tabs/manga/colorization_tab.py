"""Manga Colorization tab (roadmap §6.1, issue #195).

Exercises the Levin scribble colorizer (backend/src/manga/colorization.py,
issue #186) end-to-end through the layered canvas editor (issue #190):
load a grayscale/line-art page, paint colored scribbles, run the solver off
the UI thread, and view the result. Only the Scribble (Levin) mode is wired
up in this first pass -- the roadmap's other colorization modes
(screentone-aware level-set #187, Optimal-Transport reference #188,
graph-QP reference #189) are separate, not-yet-implemented backends; the
mode selector is left in place (single entry, disabled placeholder text on
the others) so this tab doesn't need reshaping again once they land.

New feature, not code motion.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ...constants import DIALOG_OPTS
from ...elements.manga import MangaCanvasEditor
from ...helpers.manga import ColorizeWorker
from ...utils.image_load import IMAGE_FILE_DIALOG_FILTER, load_qimage


class MangaColorizationTab(QWidget):
    """Load line art, scribble colors, and run the scribble colorizer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: ColorizeWorker | None = None
        self._image_path: str | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        btn_load = QPushButton("Load Line Art…")
        btn_load.clicked.connect(self._browse_line_art)
        toolbar.addWidget(btn_load)

        toolbar.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Scribble (Levin quadratic-cost)",
            "Screentone-aware (coming soon)",
            "Reference / Optimal-Transport (coming soon)",
            "Reference / Graph-QP (coming soon)",
        ])
        # Only the first entry has a working backend right now.
        for idx in range(1, self.mode_combo.count()):
            self.mode_combo.model().item(idx).setEnabled(False)
        toolbar.addWidget(self.mode_combo)

        toolbar.addWidget(QLabel("Pen Color:"))
        self.btn_pen_color = QPushButton()
        self.btn_pen_color.setFixedWidth(40)
        self._pen_color = QColor(220, 40, 40)
        self._update_pen_color_swatch()
        self.btn_pen_color.clicked.connect(self._pick_pen_color)
        toolbar.addWidget(self.btn_pen_color)

        toolbar.addWidget(QLabel("Pen Width:"))
        self.pen_width_slider = QSlider(Qt.Orientation.Horizontal)
        self.pen_width_slider.setRange(1, 60)
        self.pen_width_slider.setValue(12)
        self.pen_width_slider.setFixedWidth(120)
        self.pen_width_slider.valueChanged.connect(self._on_pen_width_changed)
        toolbar.addWidget(self.pen_width_slider)

        btn_clear = QPushButton("Clear Scribbles")
        toolbar.addWidget(btn_clear)

        self.btn_colorize = QPushButton("▶ Colorize")
        self.btn_colorize.clicked.connect(self._run_colorize)
        toolbar.addWidget(self.btn_colorize)

        btn_export = QPushButton("💾 Export…")
        btn_export.clicked.connect(self._export_result)
        toolbar.addWidget(btn_export)

        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.canvas = MangaCanvasEditor()
        layout.addWidget(self.canvas, 1)

        btn_clear.clicked.connect(self.canvas.clear_scribbles)

        self.status_label = QLabel("Load a line-art image to begin.")
        layout.addWidget(self.status_label)

    def _update_pen_color_swatch(self) -> None:
        self.btn_pen_color.setStyleSheet(f"background-color: {self._pen_color.name()};")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _browse_line_art(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Line Art Image", "", IMAGE_FILE_DIALOG_FILTER, options=DIALOG_OPTS
        )
        if not path:
            return
        image = load_qimage(path)
        if image.isNull():
            QMessageBox.warning(self, "Manga Colorization", f"Could not load image:\n{path}")
            return
        self._image_path = path
        self.canvas.set_line_art(image)
        self.status_label.setText(f"Loaded '{path}'. Paint scribbles, then click Colorize.")

    def _pick_pen_color(self) -> None:
        color = QColorDialog.getColor(self._pen_color, self, "Pen Color")
        if color.isValid():
            self._pen_color = color
            self._update_pen_color_swatch()
            self.canvas.set_pen_color(color)

    def _on_pen_width_changed(self, value: int) -> None:
        self.canvas.set_pen_width(value)

    def _run_colorize(self) -> None:
        if not self.canvas.has_line_art():
            QMessageBox.information(self, "Manga Colorization", "Load a line-art image first.")
            return
        if not self.canvas.has_scribbles():
            QMessageBox.information(self, "Manga Colorization", "Paint at least one scribble first.")
            return

        gray = self.canvas.get_line_art_gray()
        scribble_rgb = self.canvas.get_scribble_rgb()
        scribble_mask = self.canvas.get_scribble_mask()

        self.btn_colorize.setEnabled(False)
        self.status_label.setText("Colorizing… (solving the scribble system)")

        self._worker = ColorizeWorker(gray, scribble_rgb, scribble_mask)
        self._worker.finished_ok.connect(self._on_colorize_finished)
        self._worker.error.connect(self._on_colorize_error)
        self._worker.finished.connect(self._on_worker_thread_finished)
        self._worker.start()

    def _on_colorize_finished(self, result) -> None:
        self.canvas.set_result(result)
        self.status_label.setText("Colorization complete.")

    def _on_colorize_error(self, message: str) -> None:
        QMessageBox.critical(self, "Manga Colorization", f"Colorization failed:\n{message}")
        self.status_label.setText("Colorization failed.")

    def _on_worker_thread_finished(self) -> None:
        self.btn_colorize.setEnabled(True)
        self._worker = None

    def _export_result(self) -> None:
        pixmap = self.canvas.get_result_pixmap()
        if pixmap.isNull():
            QMessageBox.information(self, "Manga Colorization", "Nothing to export yet -- run Colorize first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Colorized Image", "colorized.png", "PNG Images (*.png)", options=DIALOG_OPTS
        )
        if not path:
            return
        if not pixmap.save(path):
            QMessageBox.critical(self, "Manga Colorization", f"Failed to save to:\n{path}")
        else:
            self.status_label.setText(f"Exported to '{path}'.")


__all__ = ["MangaColorizationTab"]
