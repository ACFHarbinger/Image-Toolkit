"""Input/output directory browsing, MRU menu, and the directory scan pipeline.

Extracted from ``codec_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from .....utils.sort_utils import natural_sort_key


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
            self.scan_directory_visual()

    def _navigate_to_dir(self, path: str) -> None:
        if not os.path.isdir(path):
            return
        self.input_path.setText(path)
        self.last_browsed_dir = path
        self._add_recent_dir(path)
        self.scan_directory_visual()

    def _show_recent_dirs_menu(self) -> None:
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
        """Lists candidate video files by extension only. Codec filtering (if
        any source-codec filters are active) happens after this, once each
        file's codec has been probed -- see scan_directory_visual()."""
        p = self.input_path.text().strip()
        if not p or not os.path.isdir(p):
            return []

        vid_formats = [f.lstrip(".").lower() for f in SUPPORTED_VIDEO_FORMATS]
        paths = []
        from gui.src.windows.settings.app_settings import AppSettings
        if AppSettings.recursive_scan():
            for root, _, files in os.walk(p):
                for file in files:
                    file_ext = os.path.splitext(file)[1].lstrip(".").lower()
                    if file_ext in vid_formats:
                        paths.append(os.path.join(root, file))
        else:
            with os.scandir(p) as it:
                for entry in it:
                    if entry.is_file():
                        file_ext = os.path.splitext(entry.name)[1].lstrip(".").lower()
                        if file_ext in vid_formats:
                            paths.append(entry.path)
        return paths

    @Slot()
    def scan_directory_visual(self):
        # Serialize overlapping switches -- see FormatSubTab's
        # scan_directory_visual() for the full rationale (issue #81).
        if getattr(self, "_scan_visual_busy", False):
            self._scan_visual_pending = True
            return
        self._scan_visual_busy = True
        QTimer.singleShot(400, self._settle_scan_visual)

        paths = self.collect_paths()
        if not paths:
            QMessageBox.information(self, "No Files", "No matching video files found.")
            self.clear_galleries()
            return

        if not self.selected_video_codecs and not self.selected_audio_codecs:
            self.start_loading_thumbnails(sorted(paths, key=natural_sort_key))
            return

        self._start_codec_probe_scan(paths)

    def _settle_scan_visual(self) -> None:
        self._scan_visual_busy = False
        if getattr(self, "_scan_visual_pending", False):
            self._scan_visual_pending = False
            QTimer.singleShot(0, self.scan_directory_visual)


__all__ = ["_DirectoryBrowseMixin"]
