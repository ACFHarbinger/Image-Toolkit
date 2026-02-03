import os

from typing import Optional
from screeninfo import Monitor
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import (
    QPixmap,
    QDragEnterEvent,
    QDropEvent,
    QDragMoveEvent,
    QDragLeaveEvent,
    QMouseEvent,
    QDrag,
    QResizeEvent,
)
from PySide6.QtWidgets import QLabel, QMenu, QApplication
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS


class MonitorDropWidget(QLabel):
    """
    A custom QLabel that acts as a drop target for images,
    displays monitor info, and shows a preview of the dropped image.
    """

    # Emits (monitor_id, image_path) when an image is successfully dropped
    image_dropped = Signal(str, str)

    # Emits monitor_id when the widget is double-clicked
    double_clicked = Signal(str)

    # Emits monitor_id when the 'Clear Monitor' right-click action is selected
    clear_requested_id = Signal(str)

    # Emits (source_id, target_id) when a 'Swap Wallpapers' target is selected
    swap_requested_id = Signal(str, str)

    def __init__(self, monitor: Monitor, monitor_id: str):
        super().__init__()
        self.monitor = monitor
        self.monitor_id = monitor_id
        self.image_path: Optional[str] = None
        self.drag_start_position = None
        self.other_monitors: list[tuple[str, str]] = []  # Added for multi-monitor swap

        # --- NEW STATE TRACKERS ---
        self._current_pixmap: Optional[QPixmap] = None
        # Stores the original QPixmap (thumbnail or image) to enable proper resizing.
        # --- END NEW STATE TRACKERS ---

        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(220, 160)
        self.setWordWrap(True)
        self.setFixedHeight(160)

        self.update_text()
        self.default_style = """
            QLabel {
                background-color: #36393f;
                border: 2px dashed #4f545c;
                border-radius: 8px;
                color: #b9bbbe;
                font-size: 14px;
            }
            QLabel[dragging="true"] {
                border: 2px solid #5865f2;
                background-color: #40444b;
            }
        """
        self.setStyleSheet(self.default_style)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        clear_action = menu.addAction("Clear All Images (Current and Queue)")
        clear_action.triggered.connect(
            lambda: self.clear_requested_id.emit(self.monitor_id)
        )

        menu.addSeparator()
        if self.other_monitors:
            swap_menu = menu.addMenu("Swap Wallpapers with...")
            for target_id, target_name in self.other_monitors:
                action = swap_menu.addAction(f"{target_name} (ID: {target_id})")
                action.triggered.connect(
                    lambda _, tid=target_id: self.swap_requested_id.emit(
                        self.monitor_id, tid
                    )
                )
        else:
            # Fallback for 2-monitor legacy case or if targets not populated
            swap_action = menu.addAction("Swap Wallpapers (Monitor switch)")
            swap_action.triggered.connect(
                lambda: self.swap_requested_id.emit(
                    self.monitor_id, ""
                )  # Handle empty in receiver
            )

        menu.exec(event.globalPos())

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.monitor_id)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton):
            return
        if not self.drag_start_position:
            return
        if (
            event.pos() - self.drag_start_position
        ).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.monitor_id)
        drag.setMimeData(mime_data)

        pixmap = self.grab()
        drag.setPixmap(pixmap.scaledToWidth(200, Qt.SmoothTransformation))
        drag.setHotSpot(event.pos())
        drag.exec(Qt.MoveAction)

    def update_text(self):
        monitor_name = f"Monitor {self.monitor_id}"
        if self.monitor.name:
            monitor_name = f"{monitor_name} ({self.monitor.name})"
        self.setText(f"<b>{monitor_name}</b>\n\nDrag and Drop Image Here")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.source() and isinstance(event.source(), MonitorDropWidget):
            event.ignore()
            return
        if self.has_valid_image_url(event.mimeData()):
            event.acceptProposedAction()
            self.setProperty("dragging", True)
            self.style().polish(self)
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.source() and isinstance(event.source(), MonitorDropWidget):
            event.ignore()
            return
        if self.has_valid_image_url(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        self.setProperty("dragging", False)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent):
        self.setProperty("dragging", False)
        self.style().polish(self)
        if self.has_valid_image_url(event.mimeData()):
            url = event.mimeData().urls()[0]
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                self.image_dropped.emit(self.monitor_id, file_path)
                event.acceptProposedAction()
                return
        event.ignore()

    def has_valid_image_url(self, mime_data: QMimeData) -> bool:
        if not mime_data.hasUrls():
            return False
        url = mime_data.urls()[0]
        if not url.isLocalFile():
            return False
        file_path = url.toLocalFile().lower()
        valid_exts = set(SUPPORTED_IMG_FORMATS).union(SUPPORTED_VIDEO_FORMATS)
        _, ext = os.path.splitext(file_path)
        ext_no_dot = ext.lstrip(".")
        if ext_no_dot in valid_exts or ext in valid_exts:
            return True
        return False

    def handle_custom_drop(self, file_path: str):
        """
        Handle a drop from the custom drag system.
        Called directly by DraggableLabel when dropped on this widget.
        """
        if os.path.isfile(file_path):
            # Validate file type
            file_path_lower = file_path.lower()
            valid_exts = set(SUPPORTED_IMG_FORMATS).union(SUPPORTED_VIDEO_FORMATS)
            _, ext = os.path.splitext(file_path_lower)
            ext_no_dot = ext.lstrip(".")

            if ext_no_dot in valid_exts or ext in valid_exts:
                self.image_dropped.emit(self.monitor_id, file_path)

    def set_image(self, file_path: Optional[str], thumbnail: Optional[QPixmap] = None):
        """
        Sets the widget's pixmap.
        Prioritizes the provided 'thumbnail' QPixmap if available (useful for videos).
        """
        self.image_path = file_path

        if not file_path:
            self.clear()
            return

        is_video = file_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))

        # 1. Determine the source pixmap
        source_pixmap = None

        if thumbnail and not thumbnail.isNull():
            # Source 1: Provided thumbnail (Async result or cache hit)
            source_pixmap = thumbnail
        else:
            # Source 2: Try to load from file (Only useful for non-video files)
            if not is_video:
                # Use QImageReader logic or simple QPixmap but check file existence first
                if os.path.exists(file_path):
                    temp_pixmap = QPixmap(file_path)
                    if not temp_pixmap.isNull():
                        source_pixmap = temp_pixmap

        # 2. Update internal state and display
        if source_pixmap and not source_pixmap.isNull():
            # Success: Store original pixmap and scale it for display
            self._current_pixmap = source_pixmap
            scaled_pixmap = source_pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

            self.setPixmap(scaled_pixmap)
            self.setText(
                ""
            )  # <--- CRITICAL: Clears any previous text, including "Loading..."

            # Apply border style
            if is_video:
                self.setStyleSheet(
                    """
                    QLabel { 
                        background-color: #36393f; 
                        border: 2px solid #3498db; 
                        border-radius: 8px;
                    }
                """
                )
            else:
                self.setStyleSheet(self.default_style)
            return

        # 3. Fallback (No thumbnail/image found)
        self._current_pixmap = None
        self.setPixmap(QPixmap())

        if is_video:
            # Video Fallback (If thumbnail is None, or generation failed)
            monitor_name = f"Monitor {self.monitor_id}"
            if self.monitor.name:
                monitor_name = f"{monitor_name} ({self.monitor.name})"

            filename = os.path.basename(file_path)
            self.setText(f"<b>{monitor_name}</b>\n\n🎥 VIDEO SET:\n{filename}")
            self.setStyleSheet(
                """
                QLabel { 
                    background-color: #2c3e50; 
                    border: 2px solid #3498db; 
                    color: #ecf0f1; 
                    font-size: 13px; 
                    border-radius: 8px;
                }
            """
            )
        else:
            # Error State or Default Drag and Drop text
            self.image_path = None
            self.update_text()  # Sets the default "Drag and Drop Image Here" text
            self.setStyleSheet(self.default_style)

    def clear(self):
        self.image_path = None
        self._current_pixmap = None  # Clear cached pixmap
        self.setPixmap(QPixmap())
        self.update_text()
        self.setStyleSheet(self.default_style)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)

        # --- CRITICAL FIX: Rescale internal pixmap without reloading ---
        if self._current_pixmap and not self._current_pixmap.isNull():
            scaled_pixmap = self._current_pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
        # --- END CRITICAL FIX ---
