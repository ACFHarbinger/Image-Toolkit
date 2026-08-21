from gui.src.components.labels.metadata_overlay import MetadataOverlay
import contextlib
import os
from typing import Callable, Optional

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel


class ClickableLabel(QLabel):
    """A QLabel that emits a signal with its associated file path when clicked."""

    path_clicked = Signal(str)
    path_double_clicked = Signal(str)
    path_right_clicked = Signal(QPoint, str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.path = file_path
        self.img_label = None
        self.style_callback = None  # Storage for the styling function
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setToolTip(os.path.basename(self.path))
        self.setFixedSize(100, 100)

        self.setStyleSheet(
            "background-color: rgba(20, 24, 32, 0.35); border: 1px dashed rgba(255, 255, 255, 0.15); color: #b9bbbe;"
        )

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.setMouseTracking(True)
        # Hover highlight (GUI/UX §2.24A)
        self._hovered = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self._metadata_overlay = MetadataOverlay(self.path, self)

        self.customContextMenuRequested.connect(self._emit_right_click_signal)

    def set_image_label(self, label: QLabel):
        """
        Set the image label for the clickable label.

        Args:
            label (QLabel): The image label to set.
        """
        self.img_label = label

    def get_pixmap(self) -> Optional[QPixmap]:
        """Safely retrieve the pixmap, handling potential destruction."""
        target = self.img_label if self.img_label else self
        try:
            return target.pixmap()
        except RuntimeError:
            return None

    def set_selected_style(self, is_selected: bool, callback: Optional[Callable] = None, target_label: Optional[QLabel] = None):
        """Safely update the style."""
        if callback:
            self.style_callback = callback
        if target_label:
            self.img_label = target_label

        if self.style_callback and self.img_label:
            # Pass the label we want to style, not self
            with contextlib.suppress(RuntimeError):
                self.style_callback(self.img_label, is_selected)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        if hasattr(self, '_metadata_overlay'):
            self._metadata_overlay.resize(self.size())
            self._metadata_overlay.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        if hasattr(self, '_metadata_overlay'):
            self._metadata_overlay.hide()
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._hovered:
            p = QPainter(self)
            p.setPen(QPen(QColor("#00bcd4"), 2))
            p.drawRect(1, 1, self.width() - 2, self.height() - 2)
            p.end()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.path_clicked.emit(self.path)

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.path_double_clicked.emit(self.path)
        super().mouseDoubleClickEvent(event)

    def _emit_right_click_signal(self, pos: QPoint):
        """
        Internal slot to emit the custom path_right_clicked signal
        when the native customContextMenuRequested signal fires.
        """
        self.path_right_clicked.emit(self.mapToGlobal(pos), self.path)
