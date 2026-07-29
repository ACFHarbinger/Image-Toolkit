"""Thumbnail double-click, full preview window, context menu, and delete.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox
from send2trash import send2trash  # pyrefly: ignore [untyped-import]
from shiboken6 import Shiboken as sip

from ......utils.sort_utils import natural_sort_key
from ......windows import ImagePreviewWindow


class _ImagePreviewDeleteMixin:
    """Thumbnail activation, full-size preview, right-click menu, and file delete."""

    def handle_thumbnail_double_click(self, image_path: str):
        if self._current_monitor_id is not None:
            self.on_image_dropped(self._current_monitor_id, image_path)
        else:
            self.handle_full_image_preview(image_path)

    def handle_full_image_preview(self, image_path: str):
        if image_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
            try:
                if platform.system() == "Windows":
                    start_fn = getattr(os, "startfile", None)
                    if start_fn:
                        start_fn(image_path)
                elif platform.system() == "Linux":
                    subprocess.Popen(
                        ["xdg-open", image_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    subprocess.Popen(
                        ["open", image_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            except Exception as e:
                QMessageBox.warning(
                    self, "Video Error", f"Could not launch video player: {e}"
                )
            return

        all_paths_list = (
            sorted(self.gallery_image_paths, key=natural_sort_key)
            if self.gallery_image_paths
            else [image_path]
        )
        try:
            start_index = all_paths_list.index(image_path)
        except ValueError:
            all_paths_list = [image_path]
            start_index = 0

        for win in list(self.open_image_preview_windows):
            if isinstance(win, ImagePreviewWindow) and win.image_path == image_path:
                win.activateWindow()
                return
        window = ImagePreviewWindow(
            image_path=image_path,
            db_tab_ref=None,
            parent=self,
            all_paths=all_paths_list,
            start_index=start_index,
        )
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.open_image_preview_windows = [
            w for w in self.open_image_preview_windows if not sip.isValid(w)
        ]

        def remove_closed_win(event: Any):
            self.open_image_preview_windows = [
                w
                for w in self.open_image_preview_windows
                if w != window and sip.isValid(w)
            ]
            event.accept()

        window.closeEvent = remove_closed_win
        window.show()
        self.open_image_preview_windows.append(window)

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        if getattr(self, "background_type", None) == "Solid Color":
            return
        menu = QMenu(self)

        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        view_text = "Play Video" if is_video else "View Full Size Preview"

        view_action = QAction(view_text, self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)

        if self.monitor_widgets:
            menu.addSeparator()
            add_menu = menu.addMenu("Add to Monitor Queue")
            for monitor_id, widget in self.monitor_widgets.items():
                monitor_name = widget.monitor.name
                action = QAction(f"{monitor_name} (ID: {monitor_id})", self)
                action.triggered.connect(
                    lambda checked,
                    mid=monitor_id,
                    img_path=path: self.on_image_dropped(mid, img_path)
                )
                add_menu.addAction(action)

            add_graph_menu = menu.addMenu("Add to Monitor Graph")
            for monitor_id, widget in self.monitor_widgets.items():
                monitor_name = widget.monitor.name
                action = QAction(f"{monitor_name} (ID: {monitor_id})", self)
                action.triggered.connect(
                    lambda checked,
                    mid=monitor_id,
                    img_path=path: self.add_image_to_graph(mid, img_path)
                )
                add_graph_menu.addAction(action)

        menu.addSeparator()
        delete_action = QAction("🗑️ Delete File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    @Slot(str)
    def handle_delete_image(self, path: str):
        if not path or not Path(path).exists():
            QMessageBox.warning(
                self, "Delete Error", "File not found or path is invalid."
            )
            return
        filename = os.path.basename(path)
        prefs = {}
        main_win = self.window()
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"

        reply = QMessageBox.question(
            self,
            f"Confirm {action_name}",
            f"Move to {action_name}:\n\n{filename}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
        try:
            if send_to_trash_enabled:
                send2trash(path)
            else:
                os.remove(path)

            if path in self.gallery_image_paths:
                self.gallery_image_paths.remove(path)

            if path in self.path_to_label_map:
                widget = self.path_to_label_map.pop(path)
                widget.deleteLater()

            # Remove from queues of all tabs (local and peer)
            for tab in [self] + getattr(self, "linked_tabs", []):
                if path in tab.gallery_image_paths:
                    tab.gallery_image_paths.remove(path)
                if path in tab.path_to_label_map:
                    w = tab.path_to_label_map.pop(path)
                    w.deleteLater()

            for mid in self.monitor_slideshow_queues:
                self.monitor_slideshow_queues[mid] = [
                    p for p in self.monitor_slideshow_queues[mid] if p != path
                ]
            for mid, current_path in self.monitor_image_paths.items():
                if current_path == path:
                    self.monitor_image_paths[mid] = None

            self.update_monitor_widget_ui(mid)
            self.refresh_gallery_view()
            for peer in getattr(self, "linked_tabs", []):
                peer.refresh_gallery_view()
            self.check_all_monitors_set()

            QMessageBox.information(
                self, "Success", f"File moved to {action_name}: {filename}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Deletion Failed", f"Could not delete the file: {e}"
            )


__all__ = ["_ImagePreviewDeleteMixin"]
