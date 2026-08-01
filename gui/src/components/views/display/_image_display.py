"""Thumbnail/pixmap display, selection styling, and resize rescaling.

Extracted from ``monitor_drop_view.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
from typing import Optional

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QResizeEvent


class _ImageDisplayMixin:
    """Sets/clears the displayed thumbnail and applies selection/video styling."""

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
            if not is_video and os.path.exists(file_path):
                temp_pixmap = QPixmap(file_path)
                if not temp_pixmap.isNull():
                    source_pixmap = temp_pixmap

        # 2. Update internal state and display
        if source_pixmap and not source_pixmap.isNull():
            # Success: Store original pixmap and scale it for display
            self._current_pixmap = source_pixmap
            scaled_pixmap = source_pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )

            self.setPixmap(scaled_pixmap)
            self.setText(
                ""
            )  # <--- CRITICAL: Clears any previous text, including "Loading..."

            # Apply border style
            if self.property("selected"):
                self.setStyleSheet("""
                    QLabel {
                        background-color: #2d5a3d;
                        border: 3px solid #2ecc71;
                        border-radius: 8px;
                        color: white;
                    }
                """)
            elif is_video:
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
        self._current_pixmap = None # pyrefly: ignore [bad-assignment]
        self.setPixmap(QPixmap())
        if self.property("selected"):
            self.setStyleSheet("""
                QLabel {
                    background-color: #2d5a3d;
                    border: 3px solid #2ecc71;
                    border-radius: 8px;
                    color: white;
                }
            """)
        elif is_video:
            # Video Fallback (If thumbnail is None, or generation failed)
            filename = os.path.basename(file_path)
            self.setText(f"\n\n🎥 VIDEO SET:\n{filename}")
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
        self._current_pixmap = None  # pyrefly: ignore [bad-assignment]
        self.setPixmap(QPixmap())
        self.update_text()
        if self.property("selected"):
            self.setStyleSheet("""
                QLabel {
                    background-color: #2d5a3d;
                    border: 3px solid #2ecc71;
                    border-radius: 8px;
                    color: white;
                }
            """)
        else:
            self.setStyleSheet(self.default_style)

    def set_selected(self, selected: bool):
        self.setProperty("selected", selected)
        if selected:
            self.setStyleSheet("""
                QLabel {
                    background-color: #2d5a3d;
                    border: 3px solid #2ecc71;
                    border-radius: 8px;
                    color: white;
                }
            """)
        else:
            # Restore standard style based on whether it has image/video
            if self.image_path:
                is_video = self.image_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
                if is_video:
                    self.setStyleSheet("""
                        QLabel {
                            background-color: #36393f;
                            border: 2px solid #3498db;
                            border-radius: 8px;
                        }
                    """)
                else:
                    self.setStyleSheet(self.default_style)
            else:
                self.setStyleSheet(self.default_style)
        self.style().polish(self)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)

        # --- CRITICAL FIX: Rescale internal pixmap without reloading ---
        if self._current_pixmap and not self._current_pixmap.isNull():
            scaled_pixmap = self._current_pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
        # --- END CRITICAL FIX ---


__all__ = ["_ImageDisplayMixin"]
