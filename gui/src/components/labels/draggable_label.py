import contextlib
from typing import Callable, Optional

from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDrag,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication, QLabel

from gui.src.components.labels.metadata_overlay import MetadataOverlay


class DraggableLabel(QLabel):
    """
    A QLabel that displays a thumbnail and can be dragged.
    Uses a custom drag system to allow wheel scrolling during drag.

    Can be used standalone (no QWidget wrapper required).  Mirrors the
    ClickableLabel interface: supports an optional *img_label* delegate
    for pixmap retrieval and style updates, and exposes ``get_pixmap()``
    / ``set_selected_style()`` methods that the gallery base class calls.
    """

    # Signal that emits the file path (Single Click)
    path_clicked = Signal(str)
    # Signal for Double Click
    path_double_clicked = Signal(str)
    # NEW: Signal for Right Click
    path_right_clicked = Signal(QPoint, str)

    # Custom drag signals
    drag_started = Signal(str)  # first_file_path
    drag_finished = Signal()

    def __init__(self, path: str, size: int, selection_provider=None):
        super().__init__()
        self.file_path = path
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("Loading...")
        self.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.selection_provider = selection_provider

        # ClickableLabel-compatible delegation fields
        self.img_label: Optional[QLabel] = None
        self.style_callback: Optional[Callable] = None

        # Set context menu policy to CustomContextMenu to enable right-click signal
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._emit_right_click_signal)

        # Custom drag state
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_preview_window = None

        # Hover highlight state (GUI/UX §2.24A)
        self._hovered = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self._metadata_overlay = MetadataOverlay(self.file_path, self)

    def _emit_right_click_signal(self, pos: QPoint):
        """
        Internal slot to emit the custom path_right_clicked signal
        when the native customContextMenuRequested signal fires.
        """
        # Emits the global position (required for QMenu) and the file path
        self.path_right_clicked.emit(self.mapToGlobal(pos), self.file_path)

    # ------------------------------------------------------------------
    # ClickableLabel-compatible interface (allows standalone use without
    # a QWidget container in create_card_widget).
    # ------------------------------------------------------------------

    def set_image_label(self, label: QLabel):
        """Set a delegate label whose pixmap is used by get_pixmap()."""
        self.img_label = label

    def get_pixmap(self) -> Optional[QPixmap]:
        """Safely retrieve the pixmap, handling potential destruction."""
        target = self.img_label if self.img_label else self
        try:
            return target.pixmap()
        except RuntimeError:
            return None

    def set_selected_style(
        self,
        is_selected: bool,
        callback: Optional[Callable] = None,
        target_label: Optional[QLabel] = None,
    ):
        """Safely update the selection style via a stored callback."""
        if callback:
            self.style_callback = callback
        if target_label:
            self.img_label = target_label

        if self.style_callback:
            label = self.img_label if self.img_label else self
            with contextlib.suppress(RuntimeError):
                self.style_callback(label, is_selected)

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
        """Handle mouse press - start tracking potential drag."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.pos()
            self.path_clicked.emit(self.file_path)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move - initiate a native QDrag once past threshold."""
        if not self.file_path or self.is_dragging or not self.drag_start_pos:
            return
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
        self._start_custom_drag()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.drag_start_pos = None
        super().mouseReleaseEvent(event)

    def _start_custom_drag(self):
        """Run a native QDrag carrying the selected file URLs.

        Uses QDrag rather than grabMouse() + a floating preview: on Wayland
        grabMouse() on a non-popup widget is a silent no-op ("This plugin
        supports grabbing the mouse only for popup windows"), which used to
        half-start the drag and leave every click in the app dead-ending on
        this label. The compositor owns the DnD grab for QDrag on both X11
        and Wayland. Drop targets (MonitorDropView, WallpaperGraphView) all
        accept text/uri-list natively.
        """
        files_to_drop = [self.file_path]
        if self.selection_provider:
            selected_files = self.selection_provider()
            if self.file_path in selected_files:
                files_to_drop = list(selected_files)
        files_to_drop = [p for p in files_to_drop if p]
        if not files_to_drop:
            return

        self.is_dragging = True
        self.drag_start_pos = None
        self.drag_started.emit(self.file_path)
        try:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(p) for p in files_to_drop])
            drag.setMimeData(mime)
            preview = self._create_drag_preview()
            if preview is not None and not preview.isNull():
                drag.setPixmap(preview)
                drag.setHotSpot(QPoint(preview.width() // 2, preview.height() // 2))
            drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)
        finally:
            self.is_dragging = False
            self.drag_finished.emit()

    def _create_drag_preview(self) -> QPixmap:
        """Create a pixmap for the drag preview."""
        if self.pixmap() and not self.pixmap().isNull():
            # If we have an image, use it as the drag preview
            preview = self.pixmap().scaled(
                self.width() // 2,
                self.height() // 2,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            # If dragging multiple files, draw a badge
            if self.selection_provider:
                from PySide6.QtCore import QRect

                selected_files = self.selection_provider()
                if self.file_path in selected_files and len(selected_files) > 1:
                    painter = QPainter(preview)
                    painter.setBrush(QColor(52, 152, 219, 200))  # Blue with opacity
                    painter.setPen(Qt.PenStyle.NoPen)
                    badge_rect = QRect(0, 0, 30, 30)
                    painter.drawEllipse(badge_rect)
                    painter.setPen(Qt.GlobalColor.white)
                    font = painter.font()
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(
                        badge_rect, Qt.AlignmentFlag.AlignCenter, str(len(selected_files))
                    )
                    painter.end()
            return preview
        else:
            # If no image (e.g., Video Placeholder), draw a generic "VIDEO" icon
            preview = QPixmap(100, 100)
            preview.fill(QColor("#3498db"))  # Blue background

            painter = QPainter(preview)
            painter.setPen(Qt.GlobalColor.white)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)

            text = "VIDEO"
            if self.selection_provider:
                selected_files = self.selection_provider()
                if self.file_path in selected_files and len(selected_files) > 1:
                    text = f"{len(selected_files)} ITEMS"

            painter.drawText(preview.rect(), Qt.AlignmentFlag.AlignCenter, text)
            painter.end()

            return preview

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Emits the double-click signal."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.path_double_clicked.emit(self.file_path)
        super().mouseDoubleClickEvent(event)
