from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPen,
    QPainter,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

_RADIUS = 200.0
_CENTRE = 230.0
_NODE_R = 18
_CONF_HIGH = QColor(80, 200, 80)
_CONF_MED = QColor(200, 200, 80)
_CONF_LOW = QColor(220, 80, 80)
_CONF_DIS = QColor(90, 90, 90)


def _conf_color(conf: float) -> QColor:
    if conf >= 0.7:
        return _CONF_HIGH
    if conf >= 0.5:
        return _CONF_MED
    return _CONF_LOW


def _node_positions(n: int) -> List[Tuple[float, float]]:
    if n <= 0:
        return []
    if n == 1:
        return [(_CENTRE, _CENTRE)]
    return [
        (
            _CENTRE + _RADIUS * math.cos(2 * math.pi * k / n - math.pi / 2),
            _CENTRE + _RADIUS * math.sin(2 * math.pi * k / n - math.pi / 2),
        )
        for k in range(n)
    ]


def _mst_edge_set(edges: List[dict]) -> set:
    sorted_by_conf = sorted(edges, key=lambda e: e["conf"], reverse=True)
    parent: dict[int, int] = {}

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent.get(x, x), x)
            x = parent.get(x, x)
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        parent[ra] = rb
        return True

    kept: set = set()
    for e in sorted_by_conf:
        if union(e["i"], e["j"]):
            kept.add(id(e))
    return kept


class EdgeReviewDialog(QDialog):
    _NODE_R = _NODE_R

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edge Graph Review — Stage 5")
        self.resize(960, 600)
        self._edges: List[dict] = list(data.get("edges", []))
        self._image_paths: List[str] = list(data.get("image_paths", []))
        self._enabled: List[bool] = [True] * len(self._edges)
        self._build_ui()
        self._populate()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        toolbar = QHBoxLayout()
        btn_mst = QPushButton("Keep MST Only")
        btn_mst.clicked.connect(self._apply_mst)
        btn_all = QPushButton("Enable All")
        btn_all.clicked.connect(self._enable_all)
        self._status_label = QLabel()
        self._status_label.setStyleSheet("color: #999; font-size: 10px;")
        btn_resume = QPushButton("Resume Pipeline")
        btn_resume.setDefault(True)
        btn_resume.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        for w in (btn_mst, btn_all):
            toolbar.addWidget(w)
        toolbar.addSpacing(8)
        toolbar.addWidget(self._status_label, stretch=1)
        toolbar.addWidget(btn_resume)
        toolbar.addWidget(btn_cancel)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setBackgroundBrush(QBrush(QColor(24, 24, 32)))
        self._view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        splitter.addWidget(self._view)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(["On", "From", "To", "Conf", "Method", "dx", "dy"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setMinimumWidth(260)
        self._table.setMaximumWidth(380)
        self._table.cellChanged.connect(self._on_cell_changed)
        splitter.addWidget(self._table)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, stretch=1)

    def _populate(self):
        self._scene.clear()
        edges = self._edges
        if not edges:
            self._status_label.setText("No edges.")
            self._table.setRowCount(0)
            return

        n_nodes = max(max(e["i"], e["j"]) for e in edges) + 1
        positions = _node_positions(n_nodes)

        for idx, e in enumerate(edges):
            xi, yi = positions[e["i"]]
            xj, yj = positions[e["j"]]
            enabled = self._enabled[idx]
            color = _conf_color(e["conf"]) if enabled else _CONF_DIS
            pen = QPen(color, max(1, int(1 + e["conf"] * 4)) if enabled else 1)
            if not enabled:
                pen.setStyle(Qt.PenStyle.DashLine)
            item = self._scene.addLine(xi, yi, xj, yj, pen)
            item.setToolTip(
                f"Edge {e['i']}→{e['j']}  conf={e['conf']:.3f}\n"
                f"dx={e['dx']:+.1f}  dy={e['dy']:+.1f}  method={e['method']}"
            )

        r = self._NODE_R
        for k, (x, y) in enumerate(positions):
            pen = QPen(QColor(180, 210, 255, 200), 1)
            brush = QBrush(QColor(50, 100, 190, 200))
            self._scene.addEllipse(x - r, y - r, 2 * r, 2 * r, pen, brush)
            label_text = str(k)
            if 0 <= k < len(self._image_paths):
                import os
                name = os.path.basename(self._image_paths[k])
                label_text += f"\n{name[:9] + '…' if len(name) > 10 else name}"
            text = self._scene.addText(label_text)
            font = QFont()
            font.setPointSize(7)
            text.setFont(font)
            text.setDefaultTextColor(QColor(230, 230, 240))
            br = text.boundingRect()
            text.setPos(x - br.width() / 2, y - br.height() / 2)

        self._view.fitInView(
            self._scene.itemsBoundingRect().adjusted(-20, -20, 20, 20),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

        self._table.blockSignals(True)
        self._table.setRowCount(len(edges))
        for row, (e, enabled) in enumerate(zip(edges, self._enabled)):
            color = _conf_color(e["conf"]) if enabled else _CONF_DIS
            chk = QTableWidgetItem()
            chk.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
            self._table.setItem(row, 0, chk)
            for col, val in enumerate([
                str(e["i"]),
                str(e["j"]),
                f"{e['conf']:.3f}",
                e["method"],
                f"{e['dx']:+.1f}",
                f"{e['dy']:+.1f}",
            ], start=1):
                cell = QTableWidgetItem(val)
                cell.setForeground(QBrush(color))
                self._table.setItem(row, col, cell)
        self._table.blockSignals(False)

        n_on = sum(self._enabled)
        n_low = sum(1 for e, en in zip(edges, self._enabled) if en and e["conf"] < 0.5)
        self._status_label.setText(
            f"{n_nodes} frames · {len(edges)} edges · {n_on} enabled · {n_low} low-conf"
        )

    def _on_cell_changed(self, row: int, col: int):
        if col != 0:
            return
        item = self._table.item(row, 0)
        if item is None:
            return
        self._enabled[row] = item.checkState() == Qt.CheckState.Checked
        self._populate()

    def _apply_mst(self):
        mst_ids = _mst_edge_set(self._edges)
        for idx, e in enumerate(self._edges):
            self._enabled[idx] = id(e) in mst_ids
        self._populate()

    def _enable_all(self):
        self._enabled = [True] * len(self._edges)
        self._populate()

    def accepted_edges(self) -> List[dict]:
        return [e for e, en in zip(self._edges, self._enabled) if en]
