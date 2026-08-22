"""Multi-image comparison view dialog (GUI/UX §2.27).

Supports comparing 2 or more images with:
- Option A: Side-by-side synchronized multi-pane view with linked pan and zoom.
- Option B: A/B Overlay view with toggle flip and opacity crossfade blending.
- Option C: Pixel difference map (|Image A - Image B|) with boost levels.
"""

from __future__ import annotations

import os
from typing import List, Optional

from PySide6.QtCore import QPoint, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QColor,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class SynchronizedImagePane(QWidget):
    """Single image pane with zoom, pan, and coordinate synchronization signals."""

    panned = Signal(QPoint)
    zoomed = Signal(float)
    clicked = Signal()

    def __init__(self, path: str, index: int, parent=None):
        super().__init__(parent)
        self.path = path
        self.index = index
        self.pixmap = QPixmap(path) if os.path.exists(path) else QPixmap()
        self.zoom_factor = 1.0
        self._rotation = 0

        # Pan state
        self._dragging = False
        self._last_mouse_pos = QPoint()

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Header badge
        self.header = QLabel()
        self.header.setStyleSheet(
            "background: rgba(30, 33, 36, 0.7); color: #dcddde; "
            "padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;"
        )
        self._update_header()
        layout.addWidget(self.header)

        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid rgba(255, 255, 255, 0.1); background: #18191c; }")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scroll_area.setWidget(self.image_label)

        # Install event filters on scroll area viewport for drag-panning
        self.scroll_area.viewport().installEventFilter(self)

        layout.addWidget(self.scroll_area, 1)

    def _update_header(self):
        if self.pixmap.isNull():
            info = f"[{self.index + 1}] {os.path.basename(self.path)} (Failed to load)"
        else:
            w, h = self.pixmap.width(), self.pixmap.height()
            size_kb = os.path.getsize(self.path) / 1024.0 if os.path.exists(self.path) else 0
            size_str = f"{size_kb / 1024.0:.1f} MB" if size_kb >= 1024 else f"{size_kb:.0f} KB"
            info = f"[{self.index + 1}] {os.path.basename(self.path)} — {w}×{h} ({size_str})"
        self.header.setText(info)

    def calculate_fit_scale(self) -> float:
        if self.pixmap.isNull() or self.pixmap.width() == 0:
            return 1.0
        avail_w = max(50, self.scroll_area.viewport().width() - 10)
        avail_h = max(50, self.scroll_area.viewport().height() - 10)
        w_ratio = avail_w / self.pixmap.width()
        h_ratio = avail_h / self.pixmap.height()
        return min(w_ratio, h_ratio, 1.0)

    def set_zoom(self, zoom: float):
        self.zoom_factor = max(0.05, min(10.0, zoom))
        self.update_display()

    def update_display(self):
        if self.pixmap.isNull():
            self.image_label.setText("Could not load image")
            return

        source = self.pixmap
        if self._rotation != 0:
            source = source.transformed(
                QTransform().rotate(self._rotation),
                Qt.TransformationMode.SmoothTransformation,
            )

        new_w = max(1, int(source.width() * self.zoom_factor))
        new_h = max(1, int(source.height() * self.zoom_factor))
        scaled = source.scaled(
            new_w, new_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.setFixedSize(scaled.size())

    def eventFilter(self, watched, event):
        if watched == self.scroll_area.viewport():
            if event.type() == QEvent_Type_MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._dragging = True
                    self._last_mouse_pos = event.pos()
                    self.clicked.emit()
                    return True
            elif event.type() == QEvent_Type_MouseMove:
                if self._dragging:
                    delta = event.pos() - self._last_mouse_pos
                    self._last_mouse_pos = event.pos()
                    self.scroll_by(-delta)
                    self.panned.emit(delta)
                    return True
            elif event.type() == QEvent_Type_MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._dragging = False
                    return True
            elif event.type() == QEvent_Type_Wheel:
                self.zoomed.emit(event.angleDelta().y())
                return True
        return super().eventFilter(watched, event)

    def scroll_by(self, delta: QPoint):
        h_bar = self.scroll_area.horizontalScrollBar()
        v_bar = self.scroll_area.verticalScrollBar()
        h_bar.setValue(h_bar.value() + delta.x())
        v_bar.setValue(v_bar.value() + delta.y())

    def set_scroll_ratios(self, rx: float, ry: float):
        h_bar = self.scroll_area.horizontalScrollBar()
        v_bar = self.scroll_area.verticalScrollBar()
        if h_bar.maximum() > 0:
            h_bar.setValue(int(rx * h_bar.maximum()))
        if v_bar.maximum() > 0:
            v_bar.setValue(int(ry * v_bar.maximum()))

    def get_scroll_ratios(self) -> tuple[float, float]:
        h_bar = self.scroll_area.horizontalScrollBar()
        v_bar = self.scroll_area.verticalScrollBar()
        rx = h_bar.value() / h_bar.maximum() if h_bar.maximum() > 0 else 0.0
        ry = v_bar.value() / v_bar.maximum() if v_bar.maximum() > 0 else 0.0
        return rx, ry


# Event type constants
QEvent_Type_MouseButtonPress = 2
QEvent_Type_MouseButtonRelease = 3
QEvent_Type_MouseMove = 5
QEvent_Type_Wheel = 31


class ImageCompareWindow(QDialog):
    """Multi-image comparison window supporting Side-by-Side, Overlay, and Difference modes."""

    MODE_SIDE_BY_SIDE = "side_by_side"
    MODE_OVERLAY = "overlay"
    MODE_DIFFERENCE = "difference"

    ZOOM_STEP = 0.1

    def __init__(
        self,
        image_paths: List[str],
        parent=None,
        initial_mode: str = "side_by_side",
    ):
        super().__init__(parent)

        self.image_paths = [p for p in image_paths if p and os.path.exists(p)]
        if not self.image_paths:
            self.image_paths = [p for p in image_paths if p]

        self.current_mode = initial_mode
        self.current_zoom_factor = 1.0
        self.sync_pan_zoom = True
        self._active_overlay_index = 0
        self._diff_multiplier = 1.0

        # Load pixmaps
        self.pixmaps = [QPixmap(p) if os.path.exists(p) else QPixmap() for p in self.image_paths]

        self.setWindowTitle(f"Image Comparison ({len(self.image_paths)} images)")
        self.setMinimumSize(600, 400)
        self.resize(1200, 800)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        self._build_ui()
        QTimer.singleShot(50, self.fit_to_window)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # 1. Top Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        # Mode selector
        self.btn_side_by_side = QPushButton("Side-by-Side (1)")
        self.btn_side_by_side.setCheckable(True)
        self.btn_side_by_side.setChecked(self.current_mode == self.MODE_SIDE_BY_SIDE)
        self.btn_side_by_side.clicked.connect(lambda: self.set_mode(self.MODE_SIDE_BY_SIDE))

        self.btn_overlay = QPushButton("A/B Overlay (2)")
        self.btn_overlay.setCheckable(True)
        self.btn_overlay.setChecked(self.current_mode == self.MODE_OVERLAY)
        self.btn_overlay.clicked.connect(lambda: self.set_mode(self.MODE_OVERLAY))

        self.btn_diff = QPushButton("Difference Map (3)")
        self.btn_diff.setCheckable(True)
        self.btn_diff.setChecked(self.current_mode == self.MODE_DIFFERENCE)
        self.btn_diff.setEnabled(len(self.image_paths) >= 2)
        self.btn_diff.clicked.connect(lambda: self.set_mode(self.MODE_DIFFERENCE))

        toolbar.addWidget(self.btn_side_by_side)
        toolbar.addWidget(self.btn_overlay)
        toolbar.addWidget(self.btn_diff)

        toolbar.addSpacing(16)

        # Zoom controls
        btn_zoom_out = QPushButton("−")
        btn_zoom_out.setFixedWidth(28)
        btn_zoom_out.clicked.connect(lambda: self.adjust_zoom(-self.ZOOM_STEP))

        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedWidth(28)
        btn_zoom_in.clicked.connect(lambda: self.adjust_zoom(self.ZOOM_STEP))

        btn_fit = QPushButton("Fit (0)")
        btn_fit.clicked.connect(self.fit_to_window)

        btn_100 = QPushButton("100%")
        btn_100.clicked.connect(lambda: self.set_zoom(1.0))

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(50)
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)

        toolbar.addWidget(btn_zoom_out)
        toolbar.addWidget(btn_zoom_in)
        toolbar.addWidget(btn_fit)
        toolbar.addWidget(btn_100)
        toolbar.addWidget(self.lbl_zoom)

        toolbar.addSpacing(16)

        # Sync toggle
        self.chk_sync = QCheckBox("Sync Pan/Zoom")
        self.chk_sync.setChecked(self.sync_pan_zoom)
        self.chk_sync.toggled.connect(self._on_sync_toggled)
        toolbar.addWidget(self.chk_sync)

        toolbar.addStretch(1)

        root.addLayout(toolbar)

        # 2. Overlay / Difference Context Sub-bar
        self.sub_bar = QFrame()
        self.sub_bar.setStyleSheet("background: rgba(40, 43, 48, 0.6); border-radius: 4px;")
        sub_layout = QHBoxLayout(self.sub_bar)
        sub_layout.setContentsMargins(8, 4, 8, 4)

        # Overlay controls
        self.btn_flip = QPushButton("Flip Image (Tab)")
        self.btn_flip.clicked.connect(self.flip_overlay_image)
        self.lbl_overlay_info = QLabel()

        self.lbl_opacity = QLabel("Opacity / Blend:")
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 100)
        self.slider_opacity.setValue(0)
        self.slider_opacity.setFixedWidth(150)
        self.slider_opacity.valueChanged.connect(self._on_opacity_slider_changed)

        # Diff controls
        self.lbl_diff_boost = QLabel("Diff Amplification:")
        self.combo_diff_boost = QComboBox()
        self.combo_diff_boost.addItems(["1×", "2×", "5×", "10×", "20×"])
        self.combo_diff_boost.currentIndexChanged.connect(self._on_diff_boost_changed)

        sub_layout.addWidget(self.btn_flip)
        sub_layout.addWidget(self.lbl_overlay_info)
        sub_layout.addSpacing(12)
        sub_layout.addWidget(self.lbl_opacity)
        sub_layout.addWidget(self.slider_opacity)
        sub_layout.addSpacing(12)
        sub_layout.addWidget(self.lbl_diff_boost)
        sub_layout.addWidget(self.combo_diff_boost)
        sub_layout.addStretch(1)

        root.addWidget(self.sub_bar)
        self._update_subbar_visibility()

        # 3. Main Display Stack
        self.stack = QStackedWidget()

        # Mode 1: Side-by-Side
        self.side_by_side_widget = QWidget()
        sbs_layout = QHBoxLayout(self.side_by_side_widget)
        sbs_layout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        self.panes: List[SynchronizedImagePane] = []
        for idx, path in enumerate(self.image_paths):
            pane = SynchronizedImagePane(path, idx, self)
            pane.panned.connect(lambda delta, p=pane: self._on_pane_panned(p, delta))
            pane.zoomed.connect(lambda delta: self.adjust_zoom(self.ZOOM_STEP if delta > 0 else -self.ZOOM_STEP))
            self.panes.append(pane)
            self.splitter.addWidget(pane)

        sbs_layout.addWidget(self.splitter)
        self.stack.addWidget(self.side_by_side_widget)

        # Mode 2 & 3: Single Viewport (Overlay & Difference)
        self.single_viewport_scroll = QScrollArea()
        self.single_viewport_scroll.setWidgetResizable(True)
        self.single_viewport_scroll.setStyleSheet("QScrollArea { border: 1px solid rgba(255, 255, 255, 0.1); background: #18191c; }")
        self.single_viewport_label = QLabel()
        self.single_viewport_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.single_viewport_scroll.setWidget(self.single_viewport_label)
        self.stack.addWidget(self.single_viewport_scroll)

        root.addWidget(self.stack, 1)

    def _update_subbar_visibility(self):
        is_overlay = self.current_mode == self.MODE_OVERLAY
        is_diff = self.current_mode == self.MODE_DIFFERENCE

        self.sub_bar.setVisible(is_overlay or is_diff)
        self.btn_flip.setVisible(is_overlay)
        self.lbl_overlay_info.setVisible(is_overlay)
        self.lbl_opacity.setVisible(is_overlay)
        self.slider_opacity.setVisible(is_overlay)

        self.lbl_diff_boost.setVisible(is_diff)
        self.combo_diff_boost.setVisible(is_diff)

        if is_overlay and self.image_paths:
            cur = self.image_paths[self._active_overlay_index]
            self.lbl_overlay_info.setText(
                f"Showing [{self._active_overlay_index + 1}/{len(self.image_paths)}] {os.path.basename(cur)}"
            )

    @Slot(str)
    def set_mode(self, mode: str):
        self.current_mode = mode
        self.btn_side_by_side.setChecked(mode == self.MODE_SIDE_BY_SIDE)
        self.btn_overlay.setChecked(mode == self.MODE_OVERLAY)
        self.btn_diff.setChecked(mode == self.MODE_DIFFERENCE)

        self._update_subbar_visibility()

        if mode == self.MODE_SIDE_BY_SIDE:
            self.stack.setCurrentWidget(self.side_by_side_widget)
            self._update_all_panes()
        elif mode == self.MODE_OVERLAY:
            self.stack.setCurrentWidget(self.single_viewport_scroll)
            self._render_overlay()
        elif mode == self.MODE_DIFFERENCE:
            self.stack.setCurrentWidget(self.single_viewport_scroll)
            self._render_difference()

    def _on_sync_toggled(self, checked: bool):
        self.sync_pan_zoom = checked
        if checked and self.panes:
            rx, ry = self.panes[0].get_scroll_ratios()
            for p in self.panes[1:]:
                p.set_zoom(self.current_zoom_factor)
                p.set_scroll_ratios(rx, ry)

    def _on_pane_panned(self, source_pane: SynchronizedImagePane, delta: QPoint):
        if not self.sync_pan_zoom:
            return
        rx, ry = source_pane.get_scroll_ratios()
        for p in self.panes:
            if p != source_pane:
                p.set_scroll_ratios(rx, ry)

    def adjust_zoom(self, delta: float):
        new_zoom = max(0.05, min(10.0, self.current_zoom_factor + delta))
        self.set_zoom(new_zoom)

    def set_zoom(self, zoom: float):
        self.current_zoom_factor = zoom
        self.lbl_zoom.setText(f"{int(zoom * 100)}%")

        if self.current_mode == self.MODE_SIDE_BY_SIDE:
            self._update_all_panes()
        elif self.current_mode == self.MODE_OVERLAY:
            self._render_overlay()
        elif self.current_mode == self.MODE_DIFFERENCE:
            self._render_difference()

    def fit_to_window(self):
        if self.current_mode == self.MODE_SIDE_BY_SIDE:
            if not self.panes:
                return
            min_fit = min(p.calculate_fit_scale() for p in self.panes)
            self.set_zoom(min_fit)
        else:
            if not self.pixmaps or self.pixmaps[0].isNull():
                return
            pm = self.pixmaps[0]
            avail_w = max(50, self.single_viewport_scroll.viewport().width() - 10)
            avail_h = max(50, self.single_viewport_scroll.viewport().height() - 10)
            fit = min(avail_w / pm.width(), avail_h / pm.height(), 1.0)
            self.set_zoom(fit)

    def _update_all_panes(self):
        for p in self.panes:
            p.set_zoom(self.current_zoom_factor)

    def flip_overlay_image(self):
        if not self.image_paths:
            return
        self._active_overlay_index = (self._active_overlay_index + 1) % len(self.image_paths)
        self._update_subbar_visibility()
        self._render_overlay()

    def _on_opacity_slider_changed(self, value: int):
        self._render_overlay()

    def _on_diff_boost_changed(self, idx: int):
        multipliers = [1.0, 2.0, 5.0, 10.0, 20.0]
        self._diff_multiplier = multipliers[idx] if idx < len(multipliers) else 1.0
        self._render_difference()

    def _render_overlay(self):
        if not self.pixmaps:
            return

        opacity_val = self.slider_opacity.value()
        if len(self.pixmaps) >= 2 and opacity_val > 0:
            idx_a = self._active_overlay_index
            idx_b = (idx_a + 1) % len(self.pixmaps)
            pm_a = self.pixmaps[idx_a]
            pm_b = self.pixmaps[idx_b]

            w = max(pm_a.width(), pm_b.width())
            h = max(pm_a.height(), pm_b.height())
            if w <= 0 or h <= 0:
                return

            blended = QPixmap(w, h)
            blended.fill(Qt.GlobalColor.transparent)
            painter = QPainter(blended)
            painter.setOpacity(1.0 - (opacity_val / 100.0))
            painter.drawPixmap(0, 0, pm_a)
            painter.setOpacity(opacity_val / 100.0)
            painter.drawPixmap(0, 0, pm_b)
            painter.end()
            source = blended
        else:
            source = self.pixmaps[self._active_overlay_index]

        new_w = max(1, int(source.width() * self.current_zoom_factor))
        new_h = max(1, int(source.height() * self.current_zoom_factor))
        scaled = source.scaled(new_w, new_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.single_viewport_label.setPixmap(scaled)
        self.single_viewport_label.setFixedSize(scaled.size())

    def _render_difference(self):
        if len(self.pixmaps) < 2:
            return

        pm_a = self.pixmaps[0]
        pm_b = self.pixmaps[1]

        w = max(pm_a.width(), pm_b.width())
        h = max(pm_a.height(), pm_b.height())
        if w <= 0 or h <= 0:
            return

        diff_pixmap = QPixmap(w, h)
        diff_pixmap.fill(Qt.GlobalColor.black)
        painter = QPainter(diff_pixmap)
        painter.drawPixmap(0, 0, pm_a)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Difference)
        painter.drawPixmap(0, 0, pm_b)
        painter.end()

        if self._diff_multiplier > 1.0:
            img = diff_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
            try:
                import numpy as np
                ptr = img.bits()
                arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, img.bytesPerLine()))[:, :w * 4]
                rgb = arr[:, :].reshape((h, w, 4))
                rgb[:, :, :3] = np.clip(rgb[:, :, :3].astype(np.float32) * self._diff_multiplier, 0, 255).astype(np.uint8)
                diff_pixmap = QPixmap.fromImage(img)
            except Exception:
                pass

        new_w = max(1, int(diff_pixmap.width() * self.current_zoom_factor))
        new_h = max(1, int(diff_pixmap.height() * self.current_zoom_factor))
        scaled = diff_pixmap.scaled(new_w, new_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.single_viewport_label.setPixmap(scaled)
        self.single_viewport_label.setFixedSize(scaled.size())

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_1:
            self.set_mode(self.MODE_SIDE_BY_SIDE)
            event.accept()
        elif key == Qt.Key.Key_2:
            self.set_mode(self.MODE_OVERLAY)
            event.accept()
        elif key == Qt.Key.Key_3 and len(self.image_paths) >= 2:
            self.set_mode(self.MODE_DIFFERENCE)
            event.accept()
        elif key == Qt.Key.Key_Tab or key == Qt.Key.Key_Space:
            if self.current_mode == self.MODE_OVERLAY:
                self.flip_overlay_image()
                event.accept()
            else:
                super().keyPressEvent(event)
        elif key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal:
            self.adjust_zoom(self.ZOOM_STEP)
            event.accept()
        elif key == Qt.Key.Key_Minus:
            self.adjust_zoom(-self.ZOOM_STEP)
            event.accept()
        elif key == Qt.Key.Key_0 or key == Qt.Key.Key_F:
            self.fit_to_window()
            event.accept()
        elif key == Qt.Key.Key_S:
            self.chk_sync.toggle()
            event.accept()
        elif key == Qt.Key.Key_Escape:
            self.close()
            event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = self.ZOOM_STEP if event.angleDelta().y() > 0 else -self.ZOOM_STEP
            self.adjust_zoom(delta)
            event.accept()
        else:
            super().wheelEvent(event)


__all__ = ["ImageCompareWindow", "SynchronizedImagePane"]
