from __future__ import annotations

import copy
import os
from typing import List, Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QPen,
    QPixmap,
    QPainter,
)
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

_FRAME_COLORS = [
    QColor(100, 149, 237, 110),
    QColor(100, 220, 130, 110),
    QColor(255, 165,   0, 110),
    QColor(210, 100, 210, 110),
    QColor(255, 215,   0, 110),
    QColor( 32, 178, 170, 110),
    QColor(255,  99,  71, 110),
    QColor(173, 216, 230, 110),
]
_HIGHLIGHT_PEN = QPen(QColor(255, 220, 50), 3)
_NORMAL_PEN_ALPHA = 180


def _bgr_thumb_to_qpixmap(bgr: np.ndarray, w: int, h: int) -> QPixmap:
    thumb = cv2.resize(bgr, (w, h), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


class CanvasInspectorDialog(QDialog):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Canvas Layout Inspector — Stage 8 (HITL)")
        self.resize(1040, 640)

        self._canvas_h: int = int(data["canvas_h"])
        self._canvas_w: int = int(data["canvas_w"])
        self._frame_h: int = int(data["frame_h"])
        self._frame_w: int = int(data["frame_w"])
        self._affines: List[List[List[float]]] = copy.deepcopy(data["affines"])
        self._image_paths: List[str] = list(data.get("image_paths", []))
        self._thumbnails: List[Optional[np.ndarray]] = list(data.get("thumbnails", []))
        self._nudges: List[List[float]] = [[0.0, 0.0] for _ in self._affines]
        self._frame_items: List[QGraphicsRectItem] = []
        self._selected_idx: Optional[int] = None

        self._build_ui()
        self._populate_scene()
        self._populate_list()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QColor(18, 18, 18))
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        splitter.addWidget(self._view)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(4)

        self._list = QListWidget()
        self._list.setMaximumWidth(220)
        self._list.currentRowChanged.connect(self._on_frame_selected)
        right_layout.addWidget(self._list, stretch=1)

        self._tx_label = QLabel("tx: —  ty: —")
        self._tx_label.setStyleSheet("font-size: 10px; color: #ccc;")
        right_layout.addWidget(self._tx_label)

        nudge_grid = QWidget()
        ng = QVBoxLayout(nudge_grid)
        ng.setSpacing(2)

        row_up = QHBoxLayout()
        btn_up = QPushButton("Nudge Up")
        btn_up.clicked.connect(lambda: self._nudge(0, -10))
        row_up.addStretch()
        row_up.addWidget(btn_up)
        row_up.addStretch()
        ng.addLayout(row_up)

        row_lr = QHBoxLayout()
        btn_left = QPushButton("Nudge Left")
        btn_left.clicked.connect(lambda: self._nudge(-10, 0))
        btn_right = QPushButton("Nudge Right")
        btn_right.clicked.connect(lambda: self._nudge(10, 0))
        row_lr.addWidget(btn_left)
        row_lr.addWidget(btn_right)
        ng.addLayout(row_lr)

        row_dn = QHBoxLayout()
        btn_dn = QPushButton("Nudge Down")
        btn_dn.clicked.connect(lambda: self._nudge(0, 10))
        row_dn.addStretch()
        row_dn.addWidget(btn_dn)
        row_dn.addStretch()
        ng.addLayout(row_dn)

        right_layout.addWidget(nudge_grid)

        btn_reset = QPushButton("Reset Frame")
        btn_reset.clicked.connect(self._reset_frame)
        right_layout.addWidget(btn_reset)

        splitter.addWidget(right)
        splitter.setSizes([780, 220])

        root.addWidget(splitter, stretch=1)

        bottom = QHBoxLayout()
        btn_resume = QPushButton("Resume Pipeline")
        btn_resume.setDefault(True)
        btn_resume.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        bottom.addStretch()
        bottom.addWidget(btn_resume)
        bottom.addWidget(btn_cancel)
        root.addLayout(bottom)

    def _populate_scene(self):
        self._scene.clear()
        self._frame_items = []

        border_pen = QPen(QColor(80, 80, 80, 200))
        border_pen.setWidth(2)
        self._scene.addRect(0, 0, self._canvas_w, self._canvas_h, border_pen, QColor(0, 0, 0, 0))

        fh, fw = self._frame_h, self._frame_w
        for idx, aff in enumerate(self._affines):
            tx = float(aff[0][2]) + self._nudges[idx][0]
            ty = float(aff[1][2]) + self._nudges[idx][1]

            color = _FRAME_COLORS[idx % len(_FRAME_COLORS)]
            pen = QPen(color.darker(150))
            pen.setWidth(2)

            if idx < len(self._thumbnails) and self._thumbnails[idx] is not None:
                pix = _bgr_thumb_to_qpixmap(self._thumbnails[idx], fw, fh)
                pix_item = QGraphicsPixmapItem(pix)
                pix_item.setPos(tx, ty)
                pix_item.setOpacity(0.6)
                self._scene.addItem(pix_item)

            rect_item = self._scene.addRect(tx, ty, fw, fh, pen, QBrush(color if idx >= len(self._thumbnails) or self._thumbnails[idx] is None else QColor(0, 0, 0, 0)))
            rect_item.setZValue(1)
            self._frame_items.append(rect_item)

            lbl = self._scene.addSimpleText(str(idx))
            lbl.setBrush(QBrush(QColor(255, 255, 255, 210)))
            lbl.setPos(tx + fw / 2 - lbl.boundingRect().width() / 2,
                       ty + fh / 2 - lbl.boundingRect().height() / 2)
            lbl.setZValue(2)

        self._view.fitInView(
            self._scene.itemsBoundingRect().adjusted(-10, -10, 10, 10),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        self._apply_highlight()

    def _populate_list(self):
        self._list.blockSignals(True)
        self._list.clear()
        for idx in range(len(self._affines)):
            name = ""
            if idx < len(self._image_paths):
                name = os.path.basename(self._image_paths[idx])
            item = QListWidgetItem(f"{idx}: {name}")
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _on_frame_selected(self, row: int):
        self._selected_idx = row if 0 <= row < len(self._affines) else None
        self._apply_highlight()
        self._update_tx_label()

    def _apply_highlight(self):
        for idx, item in enumerate(self._frame_items):
            if idx == self._selected_idx:
                item.setPen(_HIGHLIGHT_PEN)
            else:
                color = _FRAME_COLORS[idx % len(_FRAME_COLORS)]
                pen = QPen(color.darker(150))
                pen.setWidth(2)
                item.setPen(pen)

    def _update_tx_label(self):
        idx = self._selected_idx
        if idx is None or idx >= len(self._affines):
            self._tx_label.setText("tx: —  ty: —")
            return
        aff = self._affines[idx]
        tx = float(aff[0][2]) + self._nudges[idx][0]
        ty = float(aff[1][2]) + self._nudges[idx][1]
        ndx, ndy = self._nudges[idx]
        self._tx_label.setText(f"tx: {tx:.1f}  ty: {ty:.1f}  (nudge {ndx:+.0f}, {ndy:+.0f})")

    def _nudge(self, dx: float, dy: float):
        idx = self._selected_idx
        if idx is None:
            return
        self._nudges[idx][0] += dx
        self._nudges[idx][1] += dy
        self._populate_scene()
        self._list.setCurrentRow(idx)
        self._update_tx_label()

    def _reset_frame(self):
        idx = self._selected_idx
        if idx is None:
            return
        self._nudges[idx] = [0.0, 0.0]
        self._populate_scene()
        self._list.setCurrentRow(idx)
        self._update_tx_label()

    def adjusted_affines(self) -> List[List[List[float]]]:
        result = copy.deepcopy(self._affines)
        for idx, nudge in enumerate(self._nudges):
            result[idx][0][2] += nudge[0]
            result[idx][1][2] += nudge[1]
        return result
