"""Thumbnail double-click, full preview window, context menu, and delete.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QPoint, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox, QWidget
from send2trash import send2trash  # pyrefly: ignore [untyped-import]

from ......services import PreviewContext, get_preview_service
from ......utils.sort_utils import natural_sort_key

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ....protos.wallpaper_common_base import WallpaperCommonBaseHostProtocol


class _ImagePreviewDeleteMixin:
    """Thumbnail activation, full-size preview, right-click menu, and file delete."""

    def _confirm_deletions_enabled(self: "WallpaperCommonBaseHostProtocol") -> bool:
        """Read the shared deletion-confirmation preference (§2.9D)."""
        try:
            main_win = self.window()
            if main_win and hasattr(main_win, "cached_creds"):
                return bool(
                    main_win.cached_creds.get("preferences", {}).get(
                        "confirm_deletions", True
                    )
                )
        except Exception:
            logger.debug("Suppressed Exception in _ImagePreviewDeleteMixin._confirm_deletions_enabled", exc_info=True)
        return True

    def _confirm_delete(self: "WallpaperCommonBaseHostProtocol", action_name: str, filename: str) -> bool:
        """Return whether a standalone deletion may proceed."""
        if not self._confirm_deletions_enabled():
            return True
        reply = QMessageBox.question(
            cast(QWidget, self),
            f"Confirm {action_name}",
            f"Move to {action_name}:\n\n{filename}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def handle_thumbnail_double_click(self: "WallpaperCommonBaseHostProtocol", image_path: str):
        if self._current_monitor_id is not None:
            self.on_image_dropped(self._current_monitor_id, image_path)
        else:
            self.handle_full_image_preview(image_path)

    def handle_full_image_preview(self: "WallpaperCommonBaseHostProtocol", image_path: str):
        all_paths_list = (
            sorted(self.gallery_image_paths, key=natural_sort_key)
            if self.gallery_image_paths
            else [image_path]
        )
        context = PreviewContext(
            path=image_path,
            items=all_paths_list,
            parent=cast(QWidget, self),
            on_path_changed=getattr(self, "update_preview_highlight", None),
        )
        window = get_preview_service().open_preview(context)
        if window and hasattr(self, "open_image_preview_windows") and window not in self.open_image_preview_windows:
            self.open_image_preview_windows.append(window)

    @Slot(QPoint, str)
    def show_image_context_menu(self: "WallpaperCommonBaseHostProtocol", global_pos: QPoint, path: str):
        if getattr(self, "background_type", None) == "Solid Color":
            return
        menu = QMenu(cast(QWidget, self))

        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        view_text = "Play Video" if is_video else "View Full Size Preview"

        view_action = QAction(view_text, cast(QWidget, self))
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)

        if self.monitor_widgets:
            menu.addSeparator()
            add_menu = menu.addMenu("Add to Monitor Queue")
            for monitor_id, widget in self.monitor_widgets.items():
                monitor_name = widget.monitor.name
                action = QAction(f"{monitor_name} (ID: {monitor_id})", cast(QWidget, self))
                action.triggered.connect(
                    lambda checked,
                    mid=monitor_id,
                    img_path=path: self.on_image_dropped(mid, img_path)
                )
                add_menu.addAction(action)

            add_graph_menu = menu.addMenu("Add to Monitor Graph")
            for monitor_id, widget in self.monitor_widgets.items():
                monitor_name = widget.monitor.name
                action = QAction(f"{monitor_name} (ID: {monitor_id})", cast(QWidget, self))
                action.triggered.connect(
                    lambda checked,
                    mid=monitor_id,
                    img_path=path: self.add_image_to_graph(mid, img_path)
                )
                add_graph_menu.addAction(action)

        menu.addSeparator()
        delete_action = QAction("🗑️ Delete File (Permanent)", cast(QWidget, self))
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    @Slot(str)
    def handle_delete_image(self: "WallpaperCommonBaseHostProtocol", path: str):
        if not path or not Path(path).exists():
            QMessageBox.warning(
                cast(QWidget, self), "Delete Error", "File not found or path is invalid."
            )
            return
        filename = os.path.basename(path)
        prefs = {}
        main_win = self.window()
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"

        if not self._confirm_delete(action_name, filename):
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
                cast(QWidget, self), "Success", f"File moved to {action_name}: {filename}"
            )
        except Exception as e:
            QMessageBox.critical(
                cast(QWidget, self), "Deletion Failed", f"Could not delete the file: {e}"
            )


__all__ = ["_ImagePreviewDeleteMixin"]
