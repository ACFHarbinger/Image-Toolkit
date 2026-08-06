"""Manga Animation tab (roadmap §6.2, issue #196).

Exercises the spatio-temporal animation solvers end-to-end through the
existing layered canvas editor (issue #190): load a sequence of grayscale
line-art frames, scribble colors onto a couple of "key" frames (e.g. frame 0
and the last frame -- unscribbled frames get their color solved as part of
the same combined system, see ``backend/src/manga/temporal.py``'s own
docstring), run the 3D quadratic-cost temporal propagation solver
(``colorize_scribble_sequence()``, issue #192) off the UI thread, optionally
follow up with the graph-cut temporal-coherence refinement pass
(``graph_cut_temporal_refine()``, issue #193), then scrub through and export
the result.

This is explicitly a test/exercise harness for the already-built backend
solvers (see the issue's own title), not a production animation timeline
editor -- no onion-skinning, no per-frame undo stack, no in-betweening UI.

**Frame loading**: a multi-select file picker
(``QFileDialog.getOpenFileNames``), not a directory scan -- it reuses the
same ``load_qimage``/``IMAGE_FILE_DIALOG_FILTER`` helpers the single-image
tab already uses instead of writing a new directory-walking/format-filter
path. Selected files are sorted by filename (the natural "01.png, 02.png,
..." convention for an exported frame sequence) to determine sequence order.

**Per-frame scribble store**: a single shared ``MangaCanvasEditor`` (issue
#190) is reused across frames rather than instantiating one editor per frame
-- switching frames saves the outgoing frame's scribble overlay into a small
per-index dict (``self._scribble_images``) and restores the incoming frame's
overlay (if any) directly onto the canvas's scribble layer. This reaches
into ``MangaCanvasEditor``'s private ``_scribble_qimage``/``_scribble_item``
attributes (the same attributes ``gui/test/manga/test_colorization_tab.py``
already pokes at directly, e.g. ``tab.canvas._paint_line``) rather than
adding a public "swap scribble layer" method to ``canvas_editor.py`` itself,
which is out of scope for this issue (see the module docstring's own
"whatever is simplest given the existing canvas editor's API" latitude).

**Preview**: a simple frame-index slider driving a single preview
``QLabel`` (not the editable canvas) for the solved result -- a full
video-scrubbing widget is explicitly out of scope per the issue.

New feature, not code motion.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from gui.src.constants import DIALOG_OPTS
from ..elements.canvas_editor import (
    MangaCanvasEditor,
    qimage_alpha_to_mask,
    qimage_to_rgb_array,
    rgb_array_to_qpixmap,
)
from ..helpers import AnimationColorizeWorker
from gui.src.utils.image_load import IMAGE_FILE_DIALOG_FILTER, load_qimage


def _qimage_to_gray(image: QImage) -> np.ndarray:
    """HxW uint8 grayscale array of an arbitrary loaded frame -- same BT.601
    luma weighting as ``MangaCanvasEditor.get_line_art_gray()``, just not
    bound to whichever frame the canvas currently has loaded."""
    rgb = qimage_to_rgb_array(image)
    return (rgb.astype(np.float64) @ [0.299, 0.587, 0.114]).astype(np.uint8)


class MangaAnimationTab(QWidget):
    """Load a line-art frame sequence, scribble a couple of key frames, and
    run the temporal propagation (+ optional graph-cut refinement) solvers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[AnimationColorizeWorker] = None
        self._frames: List[QImage] = []
        self._frame_paths: List[str] = []
        self._scribble_images: Dict[int, QImage] = {}
        self._current_frame_index: Optional[int] = None
        self._result_stack: Optional[np.ndarray] = None
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        btn_load = QPushButton("Load Frames…")
        btn_load.clicked.connect(self._browse_frames)
        toolbar.addWidget(btn_load)

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

        btn_clear = QPushButton("Clear Frame's Scribbles")
        btn_clear.clicked.connect(self._clear_current_scribbles)
        toolbar.addWidget(btn_clear)

        self.chk_refine = QCheckBox("Graph-cut refine")
        self.chk_refine.setToolTip(
            "Run graph_cut_temporal_refine() (issue #193) as a second pass "
            "over colorize_scribble_sequence()'s output to suppress "
            "flicker/inconsistency between frames."
        )
        toolbar.addWidget(self.chk_refine)

        self.btn_colorize = QPushButton("▶ Colorize Sequence")
        self.btn_colorize.clicked.connect(self._run_colorize)
        toolbar.addWidget(self.btn_colorize)

        btn_export = QPushButton("💾 Export…")
        btn_export.clicked.connect(self._export_result)
        toolbar.addWidget(btn_export)

        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        # -- Editing row: frame scrubber over the shared scribble canvas --
        edit_row = QHBoxLayout()
        edit_row.addWidget(QLabel("Edit frame:"))
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setRange(0, 0)
        self.frame_slider.setEnabled(False)
        self.frame_slider.valueChanged.connect(self._on_frame_slider_changed)
        edit_row.addWidget(self.frame_slider, 1)
        self.frame_label = QLabel("No frames loaded.")
        edit_row.addWidget(self.frame_label)
        layout.addLayout(edit_row)

        self.canvas = MangaCanvasEditor()
        layout.addWidget(self.canvas, 1)

        # -- Preview row: result-sequence scrubber over a plain QLabel --
        preview_row = QHBoxLayout()
        preview_row.addWidget(QLabel("Preview result:"))
        self.preview_slider = QSlider(Qt.Orientation.Horizontal)
        self.preview_slider.setRange(0, 0)
        self.preview_slider.setEnabled(False)
        self.preview_slider.valueChanged.connect(self._show_preview_frame)
        preview_row.addWidget(self.preview_slider, 1)
        self.preview_frame_label = QLabel("No result yet.")
        preview_row.addWidget(self.preview_frame_label)
        layout.addLayout(preview_row)

        self.preview_label = QLabel()
        self.preview_label.setMinimumHeight(150)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #222;")
        layout.addWidget(self.preview_label, 1)

        self.status_label = QLabel("Load a sequence of line-art frames to begin.")
        layout.addWidget(self.status_label)

    def _update_pen_color_swatch(self) -> None:
        self.btn_pen_color.setStyleSheet(f"background-color: {self._pen_color.name()};")

    # ------------------------------------------------------------------
    # Frame loading / scrubbing
    # ------------------------------------------------------------------
    def _browse_frames(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Frame Images (sorted by filename)", "", IMAGE_FILE_DIALOG_FILTER, options=DIALOG_OPTS
        )
        if not paths:
            return
        self._load_frame_paths(sorted(paths))

    def _load_frame_paths(self, paths: List[str]) -> None:
        if len(paths) < 2:
            QMessageBox.information(self, "Manga Animation", "Select at least 2 frames for a sequence.")
            return

        images: List[QImage] = []
        for path in paths:
            image = load_qimage(path)
            if image.isNull():
                QMessageBox.warning(self, "Manga Animation", f"Could not load image:\n{path}")
                return
            images.append(image)

        w0, h0 = images[0].width(), images[0].height()
        for path, image in zip(paths, images, strict=True):
            if image.width() != w0 or image.height() != h0:
                QMessageBox.warning(
                    self,
                    "Manga Animation",
                    f"All frames must share the same dimensions ({w0}x{h0}); "
                    f"'{path}' is {image.width()}x{image.height()}.",
                )
                return

        self._frames = images
        self._frame_paths = paths
        self._scribble_images = {}
        self._result_stack = None

        self.frame_slider.blockSignals(True)
        self.frame_slider.setRange(0, len(images) - 1)
        self.frame_slider.setValue(0)
        self.frame_slider.blockSignals(False)
        self.frame_slider.setEnabled(True)
        self._current_frame_index = None
        self._load_frame(0)

        self.preview_slider.setRange(0, 0)
        self.preview_slider.setEnabled(False)
        self.preview_label.clear()
        self.preview_frame_label.setText("No result yet.")

        self.status_label.setText(
            f"Loaded {len(images)} frames. Scribble a couple of key frames (e.g. the first and last), then Colorize."
        )

    def _load_frame(self, index: int) -> None:
        self._current_frame_index = index
        self.canvas.set_line_art(self._frames[index])
        stored = self._scribble_images.get(index)
        if stored is not None:
            # Restore this frame's previously-painted scribble overlay onto
            # the shared canvas -- see module docstring for why this reaches
            # into the canvas's private scribble-layer attributes.
            self.canvas._scribble_qimage = stored.copy()
            self.canvas._scribble_item.setPixmap(QPixmap.fromImage(self.canvas._scribble_qimage))
        self.frame_label.setText(f"Frame {index + 1}/{len(self._frames)}")

    def _commit_current_scribble(self) -> None:
        """Save the canvas's current scribble overlay into the per-frame
        store, so it survives switching to a different frame."""
        if self._current_frame_index is None or self.canvas._scribble_qimage is None:
            return
        self._scribble_images[self._current_frame_index] = self.canvas._scribble_qimage.copy()

    def _on_frame_slider_changed(self, value: int) -> None:
        if not self._frames or value == self._current_frame_index:
            return
        self._commit_current_scribble()
        self._load_frame(value)

    def _clear_current_scribbles(self) -> None:
        self.canvas.clear_scribbles()
        if self._current_frame_index is not None:
            self._scribble_images.pop(self._current_frame_index, None)

    # ------------------------------------------------------------------
    # Pen configuration
    # ------------------------------------------------------------------
    def _pick_pen_color(self) -> None:
        color = QColorDialog.getColor(self._pen_color, self, "Pen Color")
        if color.isValid():
            self._pen_color = color
            self._update_pen_color_swatch()
            self.canvas.set_pen_color(color)

    def _on_pen_width_changed(self, value: int) -> None:
        self.canvas.set_pen_width(value)

    # ------------------------------------------------------------------
    # Colorize
    # ------------------------------------------------------------------
    def _has_any_scribbles(self) -> bool:
        return any(
            image is not None and bool(qimage_alpha_to_mask(image).any())
            for image in self._scribble_images.values()
        )

    def _run_colorize(self) -> None:
        if len(self._frames) < 2:
            QMessageBox.information(self, "Manga Animation", "Load a frame sequence first (at least 2 frames).")
            return

        self._commit_current_scribble()

        if not self._has_any_scribbles():
            QMessageBox.information(self, "Manga Animation", "Paint at least one scribble on a key frame first.")
            return

        t_dim = len(self._frames)
        h, w = self._frames[0].height(), self._frames[0].width()

        gray_stack = np.stack([_qimage_to_gray(image) for image in self._frames], axis=0)
        scribble_rgb_stack = np.zeros((t_dim, h, w, 3), dtype=np.uint8)
        scribble_mask_stack = np.zeros((t_dim, h, w), dtype=bool)
        for index, scribble_image in self._scribble_images.items():
            scribble_rgb_stack[index] = qimage_to_rgb_array(scribble_image)
            scribble_mask_stack[index] = qimage_alpha_to_mask(scribble_image)

        self.btn_colorize.setEnabled(False)
        refine = self.chk_refine.isChecked()
        self.status_label.setText(
            "Colorizing sequence… (solving the combined 3D system"
            + (", then graph-cut refining" if refine else "")
            + ")"
        )
        self._worker = AnimationColorizeWorker(
            gray_stack, scribble_rgb_stack, scribble_mask_stack, refine=refine
        )
        self._worker.finished_ok.connect(self._on_colorize_finished)
        self._worker.error.connect(self._on_colorize_error)
        self._worker.finished.connect(self._on_worker_thread_finished)
        self._worker.start()

    def _on_colorize_finished(self, result: np.ndarray) -> None:
        self._result_stack = result
        t_dim = result.shape[0]
        self.preview_slider.blockSignals(True)
        self.preview_slider.setRange(0, t_dim - 1)
        self.preview_slider.setValue(0)
        self.preview_slider.blockSignals(False)
        self.preview_slider.setEnabled(True)
        self._show_preview_frame(0)
        self.status_label.setText("Colorization complete -- scrub the preview slider to review frames.")

    def _on_colorize_error(self, message: str) -> None:
        QMessageBox.critical(self, "Manga Animation", f"Colorization failed:\n{message}")
        self.status_label.setText("Colorization failed.")

    def _on_worker_thread_finished(self) -> None:
        self.btn_colorize.setEnabled(True)
        self._worker = None

    def _show_preview_frame(self, index: int) -> None:
        if self._result_stack is None:
            return
        pixmap = rgb_array_to_qpixmap(self._result_stack[index])
        self.preview_label.setPixmap(pixmap)
        self.preview_frame_label.setText(f"Result frame {index + 1}/{self._result_stack.shape[0]}")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export_result(self) -> None:
        if self._result_stack is None:
            QMessageBox.information(self, "Manga Animation", "Nothing to export yet -- run Colorize first.")
            return
        directory = QFileDialog.getExistingDirectory(
            self, "Export Colorized Sequence", "", DIALOG_OPTS
        )
        if not directory:
            return
        failures = []
        for i in range(self._result_stack.shape[0]):
            pixmap = rgb_array_to_qpixmap(self._result_stack[i])
            path = os.path.join(directory, f"frame_{i:04d}.png")
            if not pixmap.save(path):
                failures.append(path)
        if failures:
            QMessageBox.critical(self, "Manga Animation", f"Failed to save {len(failures)} frame(s).")
        else:
            self.status_label.setText(f"Exported {self._result_stack.shape[0]} frames to '{directory}'.")


__all__ = ["MangaAnimationTab"]
