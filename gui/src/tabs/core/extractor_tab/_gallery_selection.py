"""Extracted-frame gallery card rendering, selection, and context-menu
actions (view/reload-extraction/delete).

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Set, cast

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QMessageBox, QVBoxLayout, QWidget
from send2trash import send2trash  # pyrefly: ignore [untyped-import]

from ....components import ClickableLabel
from ....windows import ImagePreviewWindow

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class _GallerySelectionMixin:
    """Extracted-frame gallery card rendering, selection, and context menu.

    Aligned with AbstractClassSingleGallery base (#448):
    - Uses base's selected_files / path_to_label_map instead of selected_paths set
    - Uses base's selection ops (marquee, keyboard) instead of local handlers
    """

    def create_card_widget(self: "VideoExtractorSubTabHostProtocol", path: str, pixmap: Optional[QPixmap]) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        clickable_label = self.create_gallery_label(path, self.thumbnail_size)

        # Explicitly define the method on the instance
        def apply_style(is_selected: bool):
            self.update_card_style(container, is_selected)

        # Assign custom styling method for the Base class to call
        container.set_selected_style = apply_style  # type: ignore[attr-defined] # pyrefly: ignore [missing-attribute]

        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))

        if pixmap and not pixmap.isNull():
            if (
                pixmap.width() > self.thumbnail_size
                or pixmap.height() > self.thumbnail_size
            ):
                scaled = pixmap.scaled(
                    self.thumbnail_size,
                    self.thumbnail_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            else:
                # Loader thumbnails already fit the target size — avoid a
                # second smooth rescale on the GUI thread (#444).
                scaled = pixmap
            clickable_label.setPixmap(scaled)
            clickable_label.setText("")
        else:
            if is_video:
                clickable_label.setText("VIDEO")
            else:
                clickable_label.setText("Loading...")

        is_selected = path in self.selected_files
        self.update_card_style(container, is_selected)

        layout.addWidget(clickable_label)
        return container

    def update_card_pixmap(self: "VideoExtractorSubTabHostProtocol", widget: QWidget, pixmap: Optional[QPixmap], label_ref: QLabel | None = None):
        clickable_label = widget.findChild(ClickableLabel)
        if clickable_label:
            is_video = clickable_label.path.lower().endswith(
                tuple(SUPPORTED_VIDEO_FORMATS)
            )

            if pixmap and not pixmap.isNull():
                if (
                    pixmap.width() > self.thumbnail_size
                    or pixmap.height() > self.thumbnail_size
                ):
                    scaled = pixmap.scaled(
                        self.thumbnail_size,
                        self.thumbnail_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                else:
                    # Loader thumbnails already fit the target size — avoid
                    # a second smooth rescale on the GUI thread (#444).
                    scaled = pixmap
                clickable_label.setPixmap(scaled)
                clickable_label.setText("")
            else:
                if not is_video:
                    clickable_label.clear()
                    clickable_label.setText("Loading...")

            self.update_card_style(
                clickable_label, is_selected=(clickable_label.path in self.selected_files)
            )

    
    def handle_marquee_selection(self: "VideoExtractorSubTabHostProtocol", marquee_selection: Set[str], is_ctrl: bool):
        # Use base's selected_files (list) and path_to_label_map (dict) instead of selected_paths set
        if is_ctrl:
            # Subtractive selection (CTRL): Remove items in marquee from selection
            for path in marquee_selection:
                if path in self.selected_files:
                    self.selected_files.remove(path)
            # Update styles for affected cards
            for path in marquee_selection:
                widget = self.path_to_card_widget.get(path)
                if widget:
                    self.update_card_style(widget, path in self.selected_files)
        else:
            # Standard selection (No Modifiers): Replace selection with marquee
            self.selected_files = sorted(list(marquee_selection))
            # Update styles for all visible cards
            self._update_card_styles()

        self.on_selection_changed()




    @Slot(str)
    def handle_thumbnail_single_click(self: "VideoExtractorSubTabHostProtocol", image_path: str):
        # Delegate to base's toggle_selection (#448)
        self.toggle_selection(image_path)


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
            self._update_card_styles()

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
            layout_changed = False

            widgets_to_delete = []

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

                    if path in self.path_to_card_widget:
                        widget = self.path_to_card_widget.pop(path)
                        if widget:
                            widgets_to_delete.append(widget)
                            layout_changed = True

                except Exception as e:
                    failed.append(f"{Path(path).name}: {e}")

            self.selected_files.clear()

            if layout_changed and self.gallery_layout is not None:
                for widget in widgets_to_delete:
                    self.gallery_layout.removeWidget(widget)
                    widget.deleteLater()

                cols = self.common_calculate_columns(
                    self.gallery_scroll_area, self.approx_item_width
                )
                self.common_reflow_layout(self.gallery_layout, cols)
                self._update_pagination_ui()

            if failed:
                QMessageBox.warning(cast(QWidget, self), "Partial Deletion Failure", "\n".join(failed))

    def delete_image(self: "VideoExtractorSubTabHostProtocol", path: str):
        if path not in self.selected_files:
            self.selected_files = [path]
        self.delete_selected_images()



    def _update_card_styles(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Re-evaluate and apply style to all currently visible cards."""
        for path, widget in self.path_to_card_widget.items():
            if widget:
                is_selected = path in self.selected_files
                self.update_card_style(widget, is_selected)


__all__ = ["_GallerySelectionMixin"]
