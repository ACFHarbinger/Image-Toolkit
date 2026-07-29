"""External-player preview and the per-card context menu.

Extracted from ``codec_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
import platform
import subprocess

from PySide6.QtCore import QPoint, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox


class _PreviewContextMixin:
    """Opens the video in an external player and builds the context menu."""

    @Slot(str)
    def handle_full_image_preview(self, video_path: str):
        if not os.path.exists(video_path):
            return
        try:
            if platform.system() == "Windows":
                os.startfile(video_path)  # pyrefly: ignore [missing-attribute]
            elif platform.system() == "Linux":
                subprocess.Popen(
                    ["xdg-open", video_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["open", video_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception as e:
            QMessageBox.warning(
                self, "Video Error", f"Could not launch video player: {e}"
            )

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)

        view_action = QAction("Open in External Player", self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)

        menu.addSeparator()

        is_selected = path in self.selected_files
        toggle_text = (
            "Deselect video from conversion"
            if is_selected
            else "Select video to convert"
        )
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)

        menu.exec(global_pos)


__all__ = ["_PreviewContextMixin"]
