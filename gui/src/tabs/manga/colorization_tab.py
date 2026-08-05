"""Manga Colorization tab (roadmap §6.1, issue #195).

Exercises the scribble colorizers (backend/src/manga/colorization.py issue
#186, screentone.py issue #187) end-to-end through the layered canvas editor
(issue #190): load a grayscale/line-art page, paint colored scribbles, run
the selected solver off the UI thread, and view the result. A third mode,
Reference / Optimal-Transport (backend/src/manga/optimal_transport.py, issue
#188), is also wired up -- it needs a second image (a colored reference
sheet) instead of scribbles, so it has its own "Load Reference…" button
(enabled only in that mode) and its own worker
(:class:`ReferenceColorizeWorker`). The roadmap's fourth mode (graph-QP
reference #189) remains an unimplemented backend; its combo entry is left in
place as a disabled placeholder so this tab doesn't need reshaping again
once it lands.

New feature, not code motion.
"""

from __future__ import annotations

from backend.src.manga import colorize_reference, colorize_scribble, colorize_scribble_screentone
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
from ...elements.manga import MangaCanvasEditor, qimage_to_rgb_array
from ...helpers.manga import ColorizeWorker, ReferenceColorizeWorker
from ...utils.image_load import IMAGE_FILE_DIALOG_FILTER, load_qimage

# Index in mode_combo -> backend colorize_fn (see ColorizeWorker's
# colorize_fn parameter). Modes not present here are disabled placeholders.
_MODE_BACKENDS = {
    0: colorize_scribble,
    1: colorize_scribble_screentone,
}

# Index in mode_combo -> backend colorize_fn taking (target_gray,
# reference_rgb, ...) instead of scribbles. These modes need a reference
# image loaded via "Load Reference…" instead of painted scribbles.
_REFERENCE_MODE_BACKENDS = {
    2: colorize_reference,
}


class MangaColorizationTab(QWidget):
    """Load line art, scribble colors, and run the scribble colorizer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: ColorizeWorker | ReferenceColorizeWorker | None = None
        self._image_path: str | None = None
        self._reference_rgb = None
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
            "Screentone-aware (Gabor texture)",
            "Reference / Optimal-Transport",
            "Reference / Graph-QP (coming soon)",
        ])
        # Entries absent from both backend maps are disabled placeholders.
        for idx in range(self.mode_combo.count()):
            if idx not in _MODE_BACKENDS and idx not in _REFERENCE_MODE_BACKENDS:
                self.mode_combo.model().item(idx).setEnabled(False)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        toolbar.addWidget(self.mode_combo)

        self.btn_load_reference = QPushButton("Load Reference…")
        self.btn_load_reference.clicked.connect(self._browse_reference)
        self.btn_load_reference.setEnabled(False)
        toolbar.addWidget(self.btn_load_reference)

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

    def _on_mode_changed(self, index: int) -> None:
        self.btn_load_reference.setEnabled(index in _REFERENCE_MODE_BACKENDS)

    def _browse_reference(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Reference Image", "", IMAGE_FILE_DIALOG_FILTER, options=DIALOG_OPTS
        )
        if not path:
            return
        image = load_qimage(path)
        if image.isNull():
            QMessageBox.warning(self, "Manga Colorization", f"Could not load reference image:\n{path}")
            return
        self._reference_rgb = qimage_to_rgb_array(image)
        self.status_label.setText(f"Loaded reference '{path}'.")

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

        mode_index = self.mode_combo.currentIndex()
        gray = self.canvas.get_line_art_gray()

        self.btn_colorize.setEnabled(False)

        if mode_index in _REFERENCE_MODE_BACKENDS:
            if self._reference_rgb is None:
                QMessageBox.information(self, "Manga Colorization", "Load a reference image first.")
                self.btn_colorize.setEnabled(True)
                return
            colorize_fn = _REFERENCE_MODE_BACKENDS[mode_index]
            self.status_label.setText("Colorizing… (solving the reference transport plan)")
            self._worker = ReferenceColorizeWorker(gray, self._reference_rgb, colorize_fn=colorize_fn)
        else:
            if not self.canvas.has_scribbles():
                QMessageBox.information(self, "Manga Colorization", "Paint at least one scribble first.")
                self.btn_colorize.setEnabled(True)
                return
            scribble_rgb = self.canvas.get_scribble_rgb()
            scribble_mask = self.canvas.get_scribble_mask()
            colorize_fn = _MODE_BACKENDS.get(mode_index, colorize_scribble)
            self.status_label.setText("Colorizing… (solving the scribble system)")
            self._worker = ColorizeWorker(gray, scribble_rgb, scribble_mask, colorize_fn=colorize_fn)

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
