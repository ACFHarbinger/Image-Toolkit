"""Image sub-tab of the Extractor tab.

Cuts a single image file that contains multiple frames (a vertical strip,
a horizontal strip, or a grid sheet) into individual frame images. The
user picks the per-frame size, the overlay draws every cut boundary on a
deep-zoom canvas (far enough in for pixel-accurate verification, far
enough out for a whole-sheet overview), and extraction only runs once the
user is happy with the boundaries.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtCore import QObject, QRect, QRectF, Qt, QThreadPool, QRunnable, Signal, Slot
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

SUPPORTED_IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.tif);;All Files (*)"

# Absolute zoom bounds for the canvas. 0.01x shows a ~40k-pixel-tall strip
# whole; 80x makes a single source pixel ~80 screen pixels wide, which is
# far past what is needed to eyeball a boundary to +/-1 px.
_MIN_SCALE = 0.01
_MAX_SCALE = 80.0


class FrameSliceCanvas(QGraphicsView):
    """Deep-zoom image canvas with a frame-boundary overlay.

    - Mouse wheel zooms (anchored under the cursor) across the full
      0.01x-80x range so the user can flip between whole-sheet overview
      and single-pixel detail quickly.
    - Left-drag pans (ScrollHandDrag).
    - Double-click toggles between fit-to-view and 1:1 pixels at the
      clicked point, which is the fastest "overview <-> pixel detail"
      round trip when checking one boundary after another.
    - At scale >= 1 smoothing is disabled so source pixels render as hard
      squares (pixel-accurate boundary verification); below 1 smoothing is
      enabled so the overview stays readable.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._overlay_items: List[Any] = []

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#1e1f22"))
        self.setStyleSheet("border: 1px solid #4f545c; border-radius: 4px;")
        self.setMinimumHeight(420)

    # --- Image / overlay management ---

    def set_image(self, image: QImage) -> None:
        self._scene.clear()
        self._overlay_items = []
        self._pixmap_item = self._scene.addPixmap(QPixmap.fromImage(image))
        self._scene.setSceneRect(QRectF(image.rect()))
        self.fit_image()

    def clear_image(self) -> None:
        self._scene.clear()
        self._overlay_items = []
        self._pixmap_item = None

    def set_frame_rects(self, rects: List[QRect], leftover: List[QRect]) -> None:
        """Redraws the cut-boundary overlay.

        `rects` are the frames that will be extracted (solid alternating
        cyan/magenta cosmetic outlines — alternating colors make shared
        edges between adjacent frames readable at any zoom); `leftover`
        marks image regions the current parameters leave uncut (dashed
        amber), so an off-by-a-few-pixels frame size is visible at the
        overview zoom before the user even zooms in.
        """
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items = []
        if self._pixmap_item is None:
            return

        colors = (QColor("#00e5ff"), QColor("#ff4dff"))
        for i, rect in enumerate(rects):
            pen = QPen(colors[i % 2])
            pen.setCosmetic(True)  # stays 1 device px wide at any zoom
            item = self._scene.addRect(QRectF(rect), pen)
            self._overlay_items.append(item)

        leftover_pen = QPen(QColor("#ffc107"))
        leftover_pen.setCosmetic(True)
        leftover_pen.setStyle(Qt.PenStyle.DashLine)
        for rect in leftover:
            item = self._scene.addRect(QRectF(rect), leftover_pen)
            self._overlay_items.append(item)

    # --- Zoom helpers ---

    def current_scale(self) -> float:
        return self.transform().m11()

    def fit_image(self) -> None:
        if self._pixmap_item is None:
            return
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._apply_render_hints()

    def zoom_1to1(self) -> None:
        self._set_absolute_scale(1.0)

    def zoom_in(self) -> None:
        self._zoom_by(1.6)

    def zoom_out(self) -> None:
        self._zoom_by(1 / 1.6)

    def _set_absolute_scale(self, scale: float) -> None:
        scale = max(_MIN_SCALE, min(_MAX_SCALE, scale))
        current = self.current_scale()
        if current > 0:
            self.scale(scale / current, scale / current)
        self._apply_render_hints()

    def _zoom_by(self, factor: float) -> None:
        target = self.current_scale() * factor
        if target < _MIN_SCALE:
            factor = _MIN_SCALE / self.current_scale()
        elif target > _MAX_SCALE:
            factor = _MAX_SCALE / self.current_scale()
        self.scale(factor, factor)
        self._apply_render_hints()

    def _apply_render_hints(self) -> None:
        smooth = self.current_scale() < 1.0
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, smooth)

    def wheelEvent(self, event):
        if self._pixmap_item is None:
            return
        # Faster per-notch factor than typical viewers: the whole point of
        # this canvas is covering a huge zoom range in few wheel ticks.
        factor = 1.3 if event.angleDelta().y() > 0 else 1 / 1.3
        self._zoom_by(factor)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if self._pixmap_item is None:
            return
        if self.current_scale() < 1.0:
            scene_pos = self.mapToScene(event.position().toPoint())
            self.zoom_1to1()
            self.centerOn(scene_pos)
        else:
            self.fit_image()
        event.accept()


class _CutWorkerSignals(QObject):
    progress = Signal(int, int)  # done, total
    finished = Signal(list)  # saved paths
    error = Signal(str)


class ImageFrameCutWorker(QRunnable):
    """Cuts the computed frame rects out of the source image off the GUI
    thread (sheets can be tens of thousands of pixels tall) and saves each
    as a PNG."""

    def __init__(self, image_path: str, rects: List[QRect], output_dir: str):
        super().__init__()
        self.signals = _CutWorkerSignals()
        self._image_path = image_path
        self._rects = rects
        self._output_dir = output_dir
        self._cancelled = False
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            image = QImage(self._image_path)
            if image.isNull():
                self.signals.error.emit(f"Could not load image: {self._image_path}")
                return

            os.makedirs(self._output_dir, exist_ok=True)
            stem = Path(self._image_path).stem
            saved: List[str] = []
            total = len(self._rects)
            for i, rect in enumerate(self._rects):
                if self._cancelled:
                    break
                frame = image.copy(rect)
                out_path = os.path.join(self._output_dir, f"{stem}_f{i + 1:03d}.png")
                if not frame.save(out_path, "PNG"):
                    self.signals.error.emit(f"Failed to save {out_path}")
                    return
                saved.append(out_path)
                self.signals.progress.emit(i + 1, total)
            self.signals.finished.emit(saved)
        except Exception as e:  # noqa: BLE001 — surfaced to the GUI
            self.signals.error.emit(str(e))


class ImageExtractorSubTab(QWidget):
    """Extractor tab's "Image" sub-tab: split a multi-frame image file into
    individual frames with visual boundary verification."""

    def __init__(self):
        super().__init__()
        self.image_path: Optional[str] = None
        self.image_size = (0, 0)
        self._frame_rects: List[QRect] = []
        self.last_browsed_dir = str(LOCAL_SOURCE_PATH)
        self.extraction_dir = Path(LOCAL_SOURCE_PATH) / "Frames"
        self._active_workers: Set[ImageFrameCutWorker] = set()

        layout = QVBoxLayout(self)

        # --- Source image ---
        src_group = QGroupBox("Source Image")
        src_layout = QHBoxLayout(src_group)
        self.line_edit_image = QLineEdit()
        self.line_edit_image.setPlaceholderText(
            "Select an image containing multiple frames (strip or grid)..."
        )
        self.line_edit_image.returnPressed.connect(
            lambda: self.load_image(self.line_edit_image.text())
        )
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self.browse_image)
        src_layout.addWidget(self.line_edit_image)
        src_layout.addWidget(self.btn_browse)
        layout.addWidget(src_group)

        # --- Output directory ---
        out_group = QGroupBox("Output Directory")
        out_layout = QHBoxLayout(out_group)
        self.line_edit_output = QLineEdit(str(self.extraction_dir))
        self.line_edit_output.setReadOnly(True)
        self.btn_browse_output = QPushButton("Change...")
        self.btn_browse_output.clicked.connect(self.browse_output_directory)
        out_layout.addWidget(self.line_edit_output)
        out_layout.addWidget(self.btn_browse_output)
        layout.addWidget(out_group)

        # --- Frame layout parameters ---
        params_group = QGroupBox("Frame Layout")
        params_layout = QHBoxLayout(params_group)

        params_layout.addWidget(QLabel("Arrangement:"))
        self.combo_arrangement = QComboBox()
        self.combo_arrangement.addItems(["Vertical", "Horizontal", "Grid"])
        self.combo_arrangement.currentTextChanged.connect(self._on_arrangement_changed)
        params_layout.addWidget(self.combo_arrangement)

        params_layout.addSpacing(12)
        self.lbl_frame_w = QLabel("Frame Width:")
        self.spin_frame_w = QSpinBox()
        self.spin_frame_w.setRange(1, 100000)
        self.spin_frame_w.setValue(512)
        self.spin_frame_w.setSuffix(" px")
        params_layout.addWidget(self.lbl_frame_w)
        params_layout.addWidget(self.spin_frame_w)

        self.lbl_frame_h = QLabel("Frame Height:")
        self.spin_frame_h = QSpinBox()
        self.spin_frame_h.setRange(1, 100000)
        self.spin_frame_h.setValue(512)
        self.spin_frame_h.setSuffix(" px")
        params_layout.addWidget(self.lbl_frame_h)
        params_layout.addWidget(self.spin_frame_h)

        params_layout.addSpacing(12)
        params_layout.addWidget(QLabel("Offset X:"))
        self.spin_offset_x = QSpinBox()
        self.spin_offset_x.setRange(0, 100000)
        self.spin_offset_x.setSuffix(" px")
        params_layout.addWidget(self.spin_offset_x)

        params_layout.addWidget(QLabel("Offset Y:"))
        self.spin_offset_y = QSpinBox()
        self.spin_offset_y.setRange(0, 100000)
        self.spin_offset_y.setSuffix(" px")
        params_layout.addWidget(self.spin_offset_y)

        params_layout.addWidget(QLabel("Spacing:"))
        self.spin_spacing = QSpinBox()
        self.spin_spacing.setRange(0, 100000)
        self.spin_spacing.setSuffix(" px")
        self.spin_spacing.setToolTip(
            "Gap between consecutive frames (both axes in Grid mode)"
        )
        params_layout.addWidget(self.spin_spacing)

        params_layout.addSpacing(12)
        self.check_include_partial = QCheckBox("Include partial last frame")
        self.check_include_partial.setToolTip(
            "Also extract the trailing region when the image size is not an "
            "exact multiple of the frame size"
        )
        params_layout.addWidget(self.check_include_partial)

        params_layout.addStretch()
        layout.addWidget(params_group)

        for spin in (
            self.spin_frame_w,
            self.spin_frame_h,
            self.spin_offset_x,
            self.spin_offset_y,
            self.spin_spacing,
        ):
            spin.valueChanged.connect(self._update_overlay)
        self.check_include_partial.toggled.connect(self._update_overlay)

        # --- Canvas + zoom controls ---
        canvas_group = QGroupBox("Frame Boundary Preview")
        canvas_layout = QVBoxLayout(canvas_group)

        zoom_bar = QHBoxLayout()
        self.btn_fit = QPushButton("Fit")
        self.btn_fit.setToolTip("Fit whole image in view (overview)")
        self.btn_1to1 = QPushButton("1:1")
        self.btn_1to1.setToolTip("100% — one image pixel per screen pixel")
        self.btn_zoom_in = QPushButton("＋")
        self.btn_zoom_out = QPushButton("－")
        # "Fit"/"1:1" need more room than the glyph-only +/- buttons so
        # their text is never elided.
        for b in (self.btn_fit, self.btn_1to1):
            b.setFixedWidth(72)
            zoom_bar.addWidget(b)
        for b in (self.btn_zoom_in, self.btn_zoom_out):
            b.setFixedWidth(48)
            zoom_bar.addWidget(b)
        zoom_hint = QLabel(
            "Wheel: zoom (cursor-anchored) · Drag: pan · Double-click: toggle overview / pixel view"
        )
        zoom_hint.setStyleSheet("color: #888; font-size: 10px; font-style: italic;")
        zoom_bar.addWidget(zoom_hint)
        zoom_bar.addStretch()
        self.info_label = QLabel("No image loaded.")
        self.info_label.setStyleSheet("color: #00BCD4; font-weight: bold;")
        zoom_bar.addWidget(self.info_label)
        canvas_layout.addLayout(zoom_bar)

        self.canvas = FrameSliceCanvas()
        canvas_layout.addWidget(self.canvas, 1)
        self.btn_fit.clicked.connect(self.canvas.fit_image)
        self.btn_1to1.clicked.connect(self.canvas.zoom_1to1)
        self.btn_zoom_in.clicked.connect(self.canvas.zoom_in)
        self.btn_zoom_out.clicked.connect(self.canvas.zoom_out)

        layout.addWidget(canvas_group, 1)

        # --- Actions ---
        actions_layout = QHBoxLayout()
        self.btn_extract = QPushButton("✂️ Cut Frames")
        self.btn_extract.setStyleSheet(
            "QPushButton { background-color: #2ecc71; color: white; font-weight: bold; padding: 6px 16px; }"
            "QPushButton:disabled { background-color: #4f545c; color: #888; }"
        )
        self.btn_extract.clicked.connect(self.extract_frames)
        self.btn_extract.setEnabled(False)
        actions_layout.addWidget(self.btn_extract)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.hide()
        actions_layout.addWidget(self.progress_bar, 1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #aaa; font-style: italic;")
        actions_layout.addWidget(self.status_label, 1)
        layout.addLayout(actions_layout)

        self._on_arrangement_changed(self.combo_arrangement.currentText())

    # --- File selection ---

    @Slot()
    def browse_image(self):
        # DontUseNativeDialog is mandatory in this app: the native GTK
        # dialog + the live JVM is a known SIGSEGV (see CLAUDE memory).
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Multi-Frame Image",
            self.last_browsed_dir,
            SUPPORTED_IMAGE_FILTER,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.last_browsed_dir = os.path.dirname(path)
            self.load_image(path)

    @Slot()
    def browse_output_directory(self):
        d = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            str(self.extraction_dir),
            QFileDialog.Option.DontUseNativeDialog
            | QFileDialog.Option.ShowDirsOnly,
        )
        if d:
            self.extraction_dir = Path(d)
            self.line_edit_output.setText(d)

    def load_image(self, path: str) -> bool:
        if not path or not os.path.isfile(path):
            return False
        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(self, "Load Error", f"Could not load image:\n{path}")
            return False

        self.image_path = path
        self.image_size = (image.width(), image.height())
        self.line_edit_image.setText(path)
        self.canvas.set_image(image)

        # A fresh image usually means fresh geometry: default the frame
        # size to something visible (square frames the width of the strip)
        # so the first overlay is never degenerate.
        w, h = self.image_size
        arrangement = self.combo_arrangement.currentText()
        if arrangement == "Vertical" and self.spin_frame_h.value() >= h:
            self.spin_frame_h.setValue(max(1, w))
        elif arrangement == "Horizontal" and self.spin_frame_w.value() >= w:
            self.spin_frame_w.setValue(max(1, h))

        self._update_overlay()
        return True

    # --- Frame geometry ---

    @Slot(str)
    def _on_arrangement_changed(self, arrangement: str):
        self.spin_frame_w.setEnabled(arrangement in ("Horizontal", "Grid"))
        self.lbl_frame_w.setEnabled(arrangement in ("Horizontal", "Grid"))
        self.spin_frame_h.setEnabled(arrangement in ("Vertical", "Grid"))
        self.lbl_frame_h.setEnabled(arrangement in ("Vertical", "Grid"))
        self._update_overlay()

    def compute_frame_rects(self) -> tuple:
        """Returns (frames, leftover) rect lists for the current parameters.

        Frames are emitted row-major. `leftover` holds the trailing partial
        region(s) not covered by a whole frame — drawn dashed, and only
        extracted when "Include partial last frame" is checked (in which
        case they are appended to `frames` by the caller via
        `_rects_for_extraction`).
        """
        img_w, img_h = self.image_size
        if img_w <= 0 or img_h <= 0:
            return [], []

        arrangement = self.combo_arrangement.currentText()
        off_x = self.spin_offset_x.value()
        off_y = self.spin_offset_y.value()
        gap = self.spin_spacing.value()

        # Per-arrangement effective frame size: strips span the full
        # remaining image extent on the non-cut axis.
        if arrangement == "Vertical":
            fw, fh = img_w - off_x, self.spin_frame_h.value()
        elif arrangement == "Horizontal":
            fw, fh = self.spin_frame_w.value(), img_h - off_y
        else:  # Grid
            fw, fh = self.spin_frame_w.value(), self.spin_frame_h.value()

        if fw <= 0 or fh <= 0:
            return [], []

        xs = [off_x] if arrangement == "Vertical" else self._axis_steps(off_x, fw, gap, img_w)
        ys = [off_y] if arrangement == "Horizontal" else self._axis_steps(off_y, fh, gap, img_h)

        frames: List[QRect] = []
        leftover: List[QRect] = []
        for y in ys:
            for x in xs:
                frames.append(QRect(x, y, fw, fh))

        # Trailing partial regions per axis (visualized dashed).
        if arrangement != "Vertical":
            last_x_end = xs[-1] + fw if xs else off_x
            if xs and last_x_end + gap < img_w:
                for y in ys:
                    leftover.append(QRect(last_x_end + gap, y, img_w - last_x_end - gap, fh))
        if arrangement != "Horizontal":
            last_y_end = ys[-1] + fh if ys else off_y
            if ys and last_y_end + gap < img_h:
                for x in xs:
                    leftover.append(QRect(x, last_y_end + gap, fw, img_h - last_y_end - gap))

        return frames, leftover

    @staticmethod
    def _axis_steps(offset: int, size: int, gap: int, limit: int) -> List[int]:
        steps = []
        pos = offset
        while pos + size <= limit:
            steps.append(pos)
            pos += size + gap
        return steps

    def _rects_for_extraction(self) -> List[QRect]:
        frames, leftover = self.compute_frame_rects()
        if self.check_include_partial.isChecked():
            img_w, img_h = self.image_size
            bounds = QRect(0, 0, img_w, img_h)
            frames += [r.intersected(bounds) for r in leftover if not r.intersected(bounds).isEmpty()]
        return frames

    @Slot()
    def _update_overlay(self):
        if self.image_path is None:
            return
        frames, leftover = self.compute_frame_rects()
        self._frame_rects = frames
        self.canvas.set_frame_rects(frames, leftover)

        img_w, img_h = self.image_size
        n = len(self._rects_for_extraction())
        self.info_label.setText(f"{img_w}×{img_h} px → {n} frame{'s' if n != 1 else ''}")
        self.btn_extract.setEnabled(n > 0)
        self.btn_extract.setText(f"✂️ Cut {n} Frame{'s' if n != 1 else ''}")

    # --- Extraction ---

    @Slot()
    def extract_frames(self):
        if not self.image_path:
            return
        rects = self._rects_for_extraction()
        if not rects:
            return

        self.btn_extract.setEnabled(False)
        self.progress_bar.setRange(0, len(rects))
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.status_label.setText("Cutting frames...")

        worker = ImageFrameCutWorker(
            self.image_path, rects, str(self.extraction_dir)
        )
        self._active_workers.add(worker)
        worker.signals.progress.connect(self._on_cut_progress)
        worker.signals.finished.connect(
            lambda paths, w=worker: self._on_cut_finished(paths, w)
        )
        worker.signals.error.connect(lambda msg, w=worker: self._on_cut_error(msg, w))
        QThreadPool.globalInstance().start(worker)

    @Slot(int, int)
    def _on_cut_progress(self, done: int, total: int):
        self.progress_bar.setValue(done)

    def _on_cut_finished(self, paths: List[str], worker: ImageFrameCutWorker):
        self._active_workers.discard(worker)
        self.progress_bar.hide()
        self.btn_extract.setEnabled(True)
        self.status_label.setText(
            f"Saved {len(paths)} frame(s) to {self.extraction_dir}"
        )

    def _on_cut_error(self, message: str, worker: ImageFrameCutWorker):
        self._active_workers.discard(worker)
        self.progress_bar.hide()
        self.btn_extract.setEnabled(True)
        self.status_label.setText("Extraction failed.")
        QMessageBox.critical(self, "Extraction Error", message)

    # --- Lifecycle / session recovery ---

    def cancel_loading(self):
        for worker in list(self._active_workers):
            worker.cancel()
        self._active_workers.clear()

    def closeEvent(self, event):
        self.cancel_loading()
        super().closeEvent(event)

    def collect(self) -> Dict[str, Any]:
        return {
            "image_path": self.image_path or "",
            "output_directory": str(self.extraction_dir),
            "arrangement": self.combo_arrangement.currentText(),
            "frame_width": self.spin_frame_w.value(),
            "frame_height": self.spin_frame_h.value(),
            "offset_x": self.spin_offset_x.value(),
            "offset_y": self.spin_offset_y.value(),
            "spacing": self.spin_spacing.value(),
            "include_partial": self.check_include_partial.isChecked(),
        }

    def set_config(self, config: Dict[str, Any]):
        arrangement = config.get("arrangement")
        if arrangement in ("Vertical", "Horizontal", "Grid"):
            self.combo_arrangement.setCurrentText(arrangement)
        for key, spin in (
            ("frame_width", self.spin_frame_w),
            ("frame_height", self.spin_frame_h),
            ("offset_x", self.spin_offset_x),
            ("offset_y", self.spin_offset_y),
            ("spacing", self.spin_spacing),
        ):
            value = config.get(key)
            if isinstance(value, int) and value >= 0:
                spin.setValue(value)
        self.check_include_partial.setChecked(bool(config.get("include_partial", False)))

        out_dir = config.get("output_directory", "")
        if out_dir and os.path.isdir(out_dir):
            self.extraction_dir = Path(out_dir)
            self.line_edit_output.setText(out_dir)

        image_path = config.get("image_path", "")
        if image_path and os.path.isfile(image_path):
            self.load_image(image_path)
