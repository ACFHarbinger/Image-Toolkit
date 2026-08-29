"""Incoming drag-and-drop handling (native Qt DnD + the custom drag system).

Extracted from ``monitor_drop_view.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from backend.src.constants import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QMimeData
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent


class _DragDropMixin:
    """Accepts/rejects and processes incoming image drops (native and custom)."""

    def dragEnterEvent(self, event: QDragEnterEvent):
        try:
            from ..monitor_drop_view import MonitorDropView

            if event.source() and isinstance(event.source(), MonitorDropView):
                event.ignore()
                return
        except Exception:
            # Never let an import hiccup here reject a legitimate drop --
            # a stale ``from .manager import`` used to raise ModuleNotFoundError
            # on every drag enter, silently killing thumbnail drag-to-monitor.
            pass
        if self.has_valid_image_url(event.mimeData()):
            event.acceptProposedAction()
            self.setProperty("dragging", True)
            self.style().polish(self)
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        try:
            from ..monitor_drop_view import MonitorDropView

            if event.source() and isinstance(event.source(), MonitorDropView):
                event.ignore()
                return
        except Exception:
            # Never let an import hiccup here reject a legitimate drop --
            # a stale ``from .manager import`` used to raise ModuleNotFoundError
            # on every drag enter, silently killing thumbnail drag-to-monitor.
            pass
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
            urls = event.mimeData().urls()
            valid_paths = []
            for url in urls:
                file_path = url.toLocalFile()
                if os.path.isfile(file_path):
                    valid_paths.append(file_path)

            if valid_paths:
                self.images_dropped.emit(self.monitor_id, valid_paths)
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
        return bool(ext_no_dot in valid_exts or ext in valid_exts)

    def handle_custom_drop(self, file_paths: list[str]):
        """
        Handle a drop from the custom drag system.
        Called directly by DraggableLabel when dropped on this widget.
        """
        valid_paths = []
        for file_path in file_paths:
            if os.path.isfile(file_path):
                # Validate file type
                file_path_lower = file_path.lower()
                valid_exts = set(SUPPORTED_IMG_FORMATS).union(SUPPORTED_VIDEO_FORMATS)
                _, ext = os.path.splitext(file_path_lower)
                ext_no_dot = ext.lstrip(".")

                if ext_no_dot in valid_exts or ext in valid_exts:
                    valid_paths.append(file_path)

        if valid_paths:
            self.images_dropped.emit(self.monitor_id, valid_paths)


__all__ = ["_DragDropMixin"]
