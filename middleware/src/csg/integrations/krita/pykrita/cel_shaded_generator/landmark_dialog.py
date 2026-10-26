"""Projection-based landmark editor using only public Krita document output."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPushButton, QVBoxLayout

from .landmarks import LandmarkCollector


class ProjectionLabel(QLabel):
    clicked = pyqtSignal(float, float)

    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self._base = pixmap
        self._points = ()
        self.setFixedSize(pixmap.size())
        self.setPixmap(pixmap)

    def set_points(self, points):
        self._points = points
        rendered = QPixmap(self._base)
        painter = QPainter(rendered)
        painter.setPen(QPen(QColor("#ff4f7b"), 3))
        painter.setBrush(QColor("#ff4f7b"))
        for index, (x, y) in enumerate(points, start=1):
            px = round(x * (rendered.width() - 1))
            py = round(y * (rendered.height() - 1))
            painter.drawEllipse(px - 5, py - 5, 10, 10)
            painter.drawText(px + 7, py - 7, str(index))
        painter.end()
        self.setPixmap(rendered)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.width() > 1 and self.height() > 1:
            self.clicked.emit(event.x() / (self.width() - 1), event.y() / (self.height() - 1))
        super().mousePressEvent(event)


class LandmarkDialog(QDialog):
    def __init__(self, document, parent=None, collector=None, title=None, crop_index=None):
        super().__init__(parent)
        self.setWindowTitle(title or "Place Front-Head Review Landmarks")
        self.collector = collector or LandmarkCollector()
        image = document.thumbnail(780 if crop_index is not None else 480, 600)
        if crop_index is not None:
            cell_width = image.width() // 5
            image = image.copy(crop_index * cell_width, 0, cell_width, image.height())
        pixmap = QPixmap.fromImage(image).scaled(
            480, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.projection = ProjectionLabel(pixmap, self)
        self.instruction = QLabel(self.collector.prompt, self)
        self.instruction.setWordWrap(True)
        undo = QPushButton("Undo Last Point", self)
        reset = QPushButton("Reset", self)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("Click landmarks in order on this current-document snapshot.", self)
        )
        layout.addWidget(self.instruction)
        layout.addWidget(self.projection)
        layout.addWidget(undo)
        layout.addWidget(reset)
        layout.addWidget(self.buttons)
        self.projection.clicked.connect(self._add_point)
        undo.clicked.connect(self._undo)
        reset.clicked.connect(self._reset)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def landmarks(self):
        return self.collector.result()

    def _add_point(self, x, y):
        if not self.collector.complete:
            self.collector.add(x, y)
            self._refresh()

    def _undo(self):
        self.collector.undo()
        self._refresh()

    def _reset(self):
        self.collector.reset()
        self._refresh()

    def _refresh(self):
        self.projection.set_points(self.collector.points)
        self.instruction.setText(self.collector.prompt)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(self.collector.complete)
