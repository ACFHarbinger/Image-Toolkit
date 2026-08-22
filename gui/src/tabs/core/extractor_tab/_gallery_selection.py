"""Extracted-frame gallery card rendering, selection, and context-menu
actions (view/reload-extraction/delete).

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Set, cast

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox, QWidget
from send2trash import send2trash  # pyrefly: ignore [untyped-import]

from ....windows import ImagePreviewWindow

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class _GallerySelectionMixin:
    """Extracted-frame gallery card rendering, selection, and context menu.

    Aligned with AbstractClassSingleGallery base (#448):
    - Uses base's selected_files / path_to_label_map instead of selected_paths set
    - Uses base's selection ops (marquee, keyboard) instead of local handlers
    """

    def _sync_selection_from_gallery(self: "VideoExtractorSubTabHostProtocol"):
        """Pull selection from the gallery's QItemSelectionModel into
        ``selected_files`` (the tab's existing single source of truth)."""
        self.selected_files = list(self.gallery.selected_files())
        self.on_selection_changed()

    def _push_selection_to_gallery(self: "VideoExtractorSubTabHostProtocol"):
        """Apply ``selected_files`` to the gallery's selection model.

        Signals are blocked on the selection model while applying so the
        clear+select below can't reentrantly trigger ``_sync_selection_from_gallery``
        and wipe ``selected_files`` mid-push."""
        sm = self.gallery.view.selectionModel()
        sm.blockSignals(True)
        try:
            self.gallery.clear_selection()
            for path in self.selected_files:
                row = self.gallery.model.row_for_path(path)
                if row >= 0:
                    sm.select(self.gallery.model.index(row, 0), sm.SelectionFlag.Select)
        finally:
            sm.blockSignals(False)

    def handle_marquee_selection(self: "VideoExtractorSubTabHostProtocol", marquee_selection: Set[str], is_ctrl: bool):
        # Marquee/drag selection is handled natively by the QListView
        # selection model; the gallery's selection_changed signal already
        # synced it. Kept for API compatibility with callers.
        self._sync_selection_from_gallery()




    @Slot(str)
    def handle_thumbnail_single_click(self: "VideoExtractorSubTabHostProtocol", image_path: str):
        # Single-click selection is handled by the view's native selection
        # model (ExtendedSelection); keep selected_files in sync.
        self._sync_selection_from_gallery()


    @Slot(str)
    def handle_thumbnail_double_click(self: "VideoExtractorSubTabHostProtocol", image_path: str):
        if image_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
            try:
                if os.name == "nt":
                    os.startfile(image_path)  # type: ignore[attr-defined]
                else:
                    subprocess.Popen(
                        ["xdg-open", image_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            except Exception as e:
                print(f"Error opening video: {e}")
            return

        for win in list(self.open_preview_windows):
            try:
                if isinstance(win, ImagePreviewWindow) and win.image_path == image_path:
                    win.activateWindow()
                    return
            except RuntimeError:
                if win in self.open_preview_windows:
                    self.open_preview_windows.remove(win)

        all_paths_list = self.current_extracted_paths
        try:
            start_index = all_paths_list.index(image_path)
        except ValueError:
            all_paths_list = [image_path]
            start_index = 0

        window = ImagePreviewWindow(
            image_path=image_path,
            db_tab_ref=None,
            parent=cast(QWidget, self),
            all_paths=all_paths_list,
            start_index=start_index,
        )
        window.path_changed.connect(self.update_preview_highlight)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.show()
        self.open_preview_windows.append(window)

    @Slot(QPoint, str)
    def show_image_context_menu(self: "VideoExtractorSubTabHostProtocol", global_pos: QPoint, path: str):
        if path not in self.selected_files:
            self.selected_files = [path]
            self._push_selection_to_gallery()

        count = len(self.selected_files)
        menu = QMenu(cast(QWidget, self))

        # Extraction History Actions
        abs_path = str(Path(path).absolute())
        metadata = self.extraction_metadata.get(abs_path)
        if metadata:
            menu.addSection("🎬 Extraction Source")

            jump_start_act = QAction("Jump to Start", cast(QWidget, self))
            jump_start_act.triggered.connect(
                lambda: self._jump_to_extraction_start(metadata)
            )
            menu.addAction(jump_start_act)

            jump_end_act = QAction("Jump to End", cast(QWidget, self))
            jump_end_act.triggered.connect(
                lambda: self._jump_to_extraction_end(metadata)
            )
            menu.addAction(jump_end_act)

            reload_act = QAction("♻️ Reload Extraction Params", cast(QWidget, self))
            reload_act.setToolTip(
                "Sets player time, cuts, and engine configs to match this run."
            )
            reload_act.triggered.connect(lambda: self._reload_extraction(metadata))
            menu.addAction(reload_act)

            menu.addSeparator()

        if count == 1 and not path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
            view_action = QAction("View Full Size", cast(QWidget, self))
            view_action.triggered.connect(
                lambda: self.handle_thumbnail_double_click(path)
            )
            menu.addAction(view_action)
            menu.addSeparator()

        del_text = f"Delete {count} Items" if count > 1 else "Delete Item"
        delete_action = QAction(del_text, cast(QWidget, self))
        delete_action.triggered.connect(self.delete_selected_images)
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def _jump_to_extraction_start(self: "VideoExtractorSubTabHostProtocol", metadata: dict):
        video_path = metadata.get("video_path")
        if video_path and os.path.exists(video_path):
            if video_path != self.video_path:
                self.load_media(video_path)
            self.media_player.setPosition(metadata.get("start_ms", 0))
            self.media_player.pause()

    def _jump_to_extraction_end(self: "VideoExtractorSubTabHostProtocol", metadata: dict):
        video_path = metadata.get("video_path")
        if video_path and os.path.exists(video_path):
            if video_path != self.video_path:
                self.load_media(video_path)
            self.media_player.setPosition(metadata.get("end_ms", 0))
            self.media_player.pause()

    def _reload_extraction(self: "VideoExtractorSubTabHostProtocol", metadata: dict):
        video_path = metadata.get("video_path")
        if video_path and os.path.exists(video_path) and video_path != self.video_path:
            self.load_media(video_path)

        # Reload Times
        self.start_time_ms = metadata.get("start_ms", 0)
        self.end_time_ms = metadata.get("end_ms", 0)
        self._update_range_labels()

        # Reload Cuts
        self.cuts_ms = metadata.get("cuts_ms", [])
        self._update_cuts_label()

        # Reload Tags
        self.tags_ms = metadata.get("tags_ms", [])
        self._update_tags_ui()

        # Reload Configs
        self.combo_extract_size.setCurrentText(metadata.get("output_size", "Native"))
        self.check_extract_vertical.setChecked(metadata.get("extract_vertical", False))
        self.spin_gif_fps.setValue(metadata.get("gif_fps", 24))
        self.check_mute_audio.setChecked(metadata.get("mute_audio", False))
        self.combo_engine.setCurrentText(metadata.get("engine", "FFmpeg"))
        self.spin_interval.setValue(metadata.get("frame_interval", 1))
        self.check_smart_extract.setChecked(metadata.get("smart_extract", False))
        self.combo_smart_method.setCurrentText(
            metadata.get("smart_method", "mpdecimate (De-duplicate)")
        )
        if "speed" in metadata:
            self.combo_speed.setCurrentText(str(metadata["speed"]))

        self.media_player.setPosition(self.start_time_ms)
        self.media_player.pause()
        self.extraction_status_label.setText("Reloaded extraction parameters.")
        self.extraction_status_label.show()

    def delete_selected_images(self: "VideoExtractorSubTabHostProtocol"):
        if not self.selected_files:
            return

        prefs = {}
        main_win = self.window()
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"

        confirm = QMessageBox.question(
            cast(QWidget, self),
            f"Confirm {action_name}",
            f"Are you sure you want to move {len(self.selected_files)} items to {action_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            failed = []
            paths_to_delete = list(self.selected_files)

            for path in paths_to_delete:
                try:
                    if send_to_trash_enabled:
                        send2trash(path)
                    else:
                        os.remove(path)
                    if path in self.current_extracted_paths:
                        self.current_extracted_paths.remove(path)
                    if path in self.gallery_image_paths:
                        self.gallery_image_paths.remove(path)
                    if hasattr(self, "master_image_paths") and path in self.master_image_paths:
                        self.master_image_paths.remove(path)
                except Exception as e:
                    failed.append(f"{Path(path).name}: {e}")

            self.selected_files.clear()
            self.gallery.clear_selection()
            # Rebuild the virtual gallery from the updated master list.
            self._perform_search()

            if failed:
                QMessageBox.warning(cast(QWidget, self), "Partial Deletion Failure", "\n".join(failed))

    def delete_image(self: "VideoExtractorSubTabHostProtocol", path: str):
        if path not in self.selected_files:
            self.selected_files = [path]
        self.delete_selected_images()



    def _update_card_styles(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Apply the current ``selected_files`` to the gallery's selection model."""
        self._push_selection_to_gallery()

    def refresh_gallery_view(self: "VideoExtractorSubTabHostProtocol"):
        """Feed the filtered path list to the virtual gallery (no page slice /
        per-card populate). Overrides the base grid refresh."""
        self.cancel_loading()
        self.clear_gallery_widgets()
        paths = self.gallery_image_paths
        if not paths:
            return
        self.gallery.set_paths(paths)

    def clear_gallery_widgets(self: "VideoExtractorSubTabHostProtocol"):
        """Clear the virtual gallery and cancel its in-flight loads."""
        self.gallery.clear()
        self.cancel_loading()


__all__ = ["_GallerySelectionMixin"]
