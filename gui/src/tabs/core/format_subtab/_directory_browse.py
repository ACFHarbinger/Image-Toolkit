"""Input/output directory browsing, MRU menu, and the directory scan pipeline.

Extracted from ``format_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from backend.src.constants import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ....utils.sort_utils import natural_sort_key


class _DirectoryBrowseMixin:
    """Directory pickers, the recent-dirs MRU menu, and the visual scan pipeline."""

    @Slot()
    def browse_directory_and_scan(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select input directory",
            self.last_browsed_dir,
            QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            self._push_dir_history(self.last_browsed_dir)
            self.input_path.setText(directory)
            self.last_browsed_dir = directory
            self._add_recent_dir(directory)
            self.qml_input_path_changed.emit(directory)
            self.scan_directory_visual()

    def _navigate_to_dir(self, path: str) -> None:
        """Virtual hook called by base-class back/forward navigation."""
        if not os.path.isdir(path):
            return
        self.input_path.setText(path)
        self.last_browsed_dir = path
        self._add_recent_dir(path)
        self._save_last_dir(path)
        if hasattr(self, "_btn_recent_dirs") and hasattr(self._btn_recent_dirs, "refresh_menu"):
            self._btn_recent_dirs.refresh_menu()
        self.qml_input_path_changed.emit(path)
        self.scan_directory_visual()

    def _show_recent_dirs_menu(self) -> None:
        """Populate and show the MRU recent-directories popup menu (§2.21D)."""
        self._recent_dirs_menu.clear()
        dirs = self._get_recent_dirs()
        if not dirs:
            act = self._recent_dirs_menu.addAction("(no recent directories)")
            act.setEnabled(False)
        else:
            for d in dirs:
                act = self._recent_dirs_menu.addAction(d)
                act.triggered.connect(
                    lambda checked=False, p=d: self._navigate_to_dir(p)
                )
        self._recent_dirs_menu.exec(
            self._btn_recent_dirs.mapToGlobal(self._btn_recent_dirs.rect().bottomLeft())
        )

    @Slot()
    def browse_output(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select output directory",
            "",
        )
        if directory:
            self.output_path.setText(directory)

    def collect_paths(self) -> list[str]:
        p = self.input_path.text().strip()
        if not p or not os.path.isdir(p):
            return []

        # Determine strict filter list
        if self.dropdown and self.selected_formats:
            input_formats = list(self.selected_formats)
        elif (
            not self.dropdown
            and hasattr(self, "input_formats")
            and self.input_formats.text().strip()
        ):
            input_formats = self.join_list_str(self.input_formats.text().strip())
        else:
            # Fallback: All supported formats (Images + Videos)
            vid_formats = [f.lstrip(".").lower() for f in SUPPORTED_VIDEO_FORMATS]
            img_formats = [f.lower() for f in SUPPORTED_IMG_FORMATS]
            input_formats = vid_formats + img_formats

        paths = []
        from gui.src.windows.settings.app_settings import AppSettings
        if AppSettings.recursive_scan():
            for root, _, files in os.walk(p):
                for file in files:
                    file_ext = os.path.splitext(file)[1].lstrip(".").lower()
                    if not input_formats or file_ext in input_formats:
                        paths.append(os.path.join(root, file))
        else:
            with os.scandir(p) as it:
                for entry in it:
                    if entry.is_file():
                        file_ext = os.path.splitext(entry.name)[1].lstrip(".").lower()
                        if not input_formats or file_ext in input_formats:
                            paths.append(entry.path)
        return paths

    @Slot()
    def scan_directory_visual(self):
        # Serialize overlapping switches (issue #81, same principle as
        # WallpaperCommonBase.populate_scan_image_gallery()): rapid,
        # back-to-back calls (e.g. quick successive directory browses)
        # would otherwise each start their own clear_galleries()/
        # start_loading_thumbnails() cycle concurrently, producing the same
        # class of heavy QObject churn under which this whole investigation's
        # crash reproduces (PySide6/Shiboken's own binding-layer bookkeeping,
        # not application logic). Unlike the Wallpaper tab's scan pipeline,
        # there's no single "fully settled" event to hook here (chunked
        # thumbnail loads have no one "all done" signal), so this uses a
        # fixed settle window instead of an event-driven one -- long enough
        # for a typical scan+dispatch to get well underway. self.input_path
        # is read fresh when the deferred call actually runs, so only the
        # *last* requested directory during a rapid burst is ever acted on.
        if getattr(self, "_scan_visual_busy", False):
            self._scan_visual_pending = True
            return
        self._scan_visual_busy = True
        QTimer.singleShot(400, self._settle_scan_visual)

        paths = self.collect_paths()
        if not paths:
            QMessageBox.information(self, "No Files", "No matching files found.")
            self.clear_galleries()
            return

        self.start_loading_thumbnails(sorted(paths, key=natural_sort_key))

    def _settle_scan_visual(self) -> None:
        self._scan_visual_busy = False
        if getattr(self, "_scan_visual_pending", False):
            self._scan_visual_pending = False
            QTimer.singleShot(0, self.scan_directory_visual)


__all__ = ["_DirectoryBrowseMixin"]
