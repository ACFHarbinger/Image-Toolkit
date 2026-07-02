from typing import Optional, Callable
from PySide6.QtWidgets import QLabel, QApplication
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QMouseEvent, QPixmap, QPainter, QColor, QCursor, QPen
from .drag_preview_window import DragPreviewWindow


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
            try:
                self.style_callback(label, is_selected)
            except RuntimeError:
                pass

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
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
        """Handle mouse move - initiate custom drag if threshold exceeded."""
        if not self.file_path:
            return

        # Check if we should start dragging
        if not self.is_dragging and self.drag_start_pos:
            # Check if moved enough to start drag (Qt default threshold is ~4 pixels)
            if (event.pos() - self.drag_start_pos).manhattanLength() < 4:
                return

            # Start custom drag
            self._start_custom_drag()

        if self.is_dragging:
            # Update drag preview position
            if self.drag_preview_window:
                self.drag_preview_window.update_position(QCursor.pos())

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release - end custom drag."""
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self._finish_custom_drag(QCursor.pos())
        super().mouseReleaseEvent(event)

    def _start_custom_drag(self):
        """Start the custom drag operation."""
        self.is_dragging = True

        # Create drag preview
        preview_pixmap = self._create_drag_preview()
        self.drag_preview_window = DragPreviewWindow(preview_pixmap)
        self.drag_preview_window.update_position(QCursor.pos())
        self.drag_preview_window.show()

        # Grab mouse to track movement even outside widget
        self.grabMouse()

        # Emit drag started signal
        self.drag_started.emit(self.file_path)

    def _finish_custom_drag(self, drop_pos: QPoint):
        """Finish the custom drag operation."""
        self.is_dragging = False
        self.drag_start_pos = None

        # Release mouse
        self.releaseMouse()

        # Hide and delete preview window
        if self.drag_preview_window:
            self.drag_preview_window.hide()
            self.drag_preview_window.deleteLater()
            self.drag_preview_window = None

        # Find widget under cursor and try to drop
        widget_under_cursor = QApplication.widgetAt(drop_pos)
        if widget_under_cursor:
            self._try_drop_on_widget(widget_under_cursor)

        # Emit drag finished signal
        self.drag_finished.emit()

    def _try_drop_on_widget(self, widget):
        """Try to drop the file on the target widget."""
        # Import here to avoid circular dependency
        from .monitor_drop_widget import MonitorDropWidget
        from PySide6.QtCore import QPointF

        # Get all files to drop
        files_to_drop = [self.file_path]
        if self.selection_provider:
            selected_files = self.selection_provider()
            if self.file_path in selected_files:
                files_to_drop = selected_files

        # Check if widget or any of its parents is a MonitorDropWidget or WallpaperGraphView
        current = widget
        while current:
            if isinstance(current, MonitorDropWidget):
                # Simulate a drop by calling the widget's method directly
                current.handle_custom_drop(files_to_drop)
                return
            if current.__class__.__name__ == "WallpaperGraphView" or (hasattr(current, "scene") and hasattr(current, "mapToScene")):
                view = current
                sc = view.scene()
                if sc and hasattr(sc, "add_node"):
                    # Map global cursor position to local viewport coordinate, then to scene
                    local_pos = view.viewport().mapFromGlobal(QCursor.pos())
                    scene_pos = view.mapToScene(local_pos)
                    for file_path in files_to_drop:
                        sc.add_node(file_path, scene_pos)
                        # Offset subsequent nodes to avoid direct stacking
                        scene_pos = QPointF(scene_pos.x() + 160, scene_pos.y())
                    return
            current = current.parentWidget()

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
