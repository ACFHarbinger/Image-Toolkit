"""Source-directory browsing/scanning and the source thumbnail gallery.

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.

Directory listing (``scan_directory()``) is a plain, synchronous
``os.scandir()`` call -- the crash class documented in
.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md was never traced
to this. Thumbnail *generation* for entries without a disk-cache hit is
dispatched via ``BatchVideoLoaderWorker`` on the global QThreadPool --
the same QRunnable architecture as VideoLoaderWorker/ImageLoaderWorker,
never implicated across 22+ rounds of that investigation (Addendum 24).
A monotonically increasing ``_extractor_scan_generation`` counter, bumped
at the start of every ``scan_directory()`` call before any widget
teardown, guards delivery of a queued batch result against a directory
switch that happened while it was still in flight.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from backend.src.core import telemetry
from PySide6.QtCore import QPoint, Qt, QTimer, Slot
from PySide6.QtGui import QAction, QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ....components import ClickableLabel, MarqueeScrollArea
from ....constants import MAX_PREVIEW_ITEMS
from ....helpers import BatchVideoLoaderWorker
from ....utils.guard.startup_probe_guard import startup_settle_remaining_ms
from ....utils.sort_utils import natural_sort_key

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class _DirectoryScanningMixin:
    """Source-directory browsing/scanning and the source media gallery."""

    def _build_directory_section(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Builds "1./1.5. Directory Selection" + "2. Source Gallery" and
        adds them to self.main_layout."""
        # 1. Directory Selection Section (Source Directory)
        dir_select_group = QGroupBox("Source Directory")
        dir_layout = QHBoxLayout(dir_select_group)

        self.line_edit_dir = QLineEdit()
        self.line_edit_dir.setPlaceholderText(
            "Select a folder containing videos or GIFs..."
        )
        self.line_edit_dir.returnPressed.connect(
            lambda: self.scan_directory(self.line_edit_dir.text())
        )

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self.browse_directory)
        self._btn_nav_back, self._btn_nav_forward = self.create_nav_history_buttons(self._navigate_to_dir)
        self._btn_recent_dirs = self.create_recent_dirs_button(self._navigate_to_dir)

        dir_layout.addWidget(self.line_edit_dir)
        dir_layout.addWidget(self.btn_browse)
        dir_layout.addWidget(self._btn_nav_back)
        dir_layout.addWidget(self._btn_nav_forward)
        dir_layout.addWidget(self._btn_recent_dirs)

        self.main_layout.addWidget(dir_select_group)

        # 1.5. Extraction Target Directory Section
        dir_set_group = QGroupBox("Output Directory")
        dir_set_layout = QHBoxLayout(dir_set_group)

        self.line_edit_extract_dir = QLineEdit(str(self.extraction_dir))
        self.line_edit_extract_dir.setReadOnly(True)

        self.btn_browse_extract = QPushButton("Change...")
        self.btn_browse_extract.clicked.connect(self.browse_extraction_directory)

        dir_set_layout.addWidget(self.line_edit_extract_dir)
        dir_set_layout.addWidget(self.btn_browse_extract)

        self.main_layout.addWidget(dir_set_group)

        # 2. Source Gallery
        self.source_group = QGroupBox("Available Media")
        source_layout = QVBoxLayout(self.source_group)

        self.source_scroll = MarqueeScrollArea()
        self.source_scroll.setWidgetResizable(True)
        self.source_scroll.setMinimumHeight(300)
        self.source_scroll.setMaximumHeight(300)

        self.source_container = QWidget()

        self.source_grid = QGridLayout(self.source_container)
        self.source_grid.setAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop
        )
        self.source_scroll.setWidget(self.source_container)

        source_layout.addWidget(self.source_scroll)
        self.main_layout.addWidget(self.source_group)

    def _navigate_to_dir(self, d: str) -> None:
        if not d or not os.path.exists(d):
            return
        self.line_edit_dir.setText(d)
        self.last_browsed_scan_dir = d
        self._add_recent_dir(d)
        self._save_last_dir(d)
        if hasattr(self, "_btn_recent_dirs") and hasattr(self._btn_recent_dirs, "refresh_menu"):
            self._btn_recent_dirs.refresh_menu()
        self.scan_directory(d)

    @Slot()
    def browse_directory(self: "VideoExtractorSubTabHostProtocol"):
        d = QFileDialog.getExistingDirectory(
            cast(QWidget, self), "Select Source Directory", self.last_browsed_scan_dir
        )
        if d:
            self._navigate_to_dir(d)

    def _load_last_extraction_dir(self: "VideoExtractorSubTabHostProtocol", default: str = "") -> str:
        from gui.src.windows.settings.app_settings import AppSettings

        return AppSettings.session(
            self.__class__.__name__, "last_extraction_dir", default
        )

    def _save_last_extraction_dir(self: "VideoExtractorSubTabHostProtocol", path: str) -> None:
        from gui.src.windows.settings.app_settings import AppSettings

        AppSettings.set_session(
            self.__class__.__name__, "last_extraction_dir", path
        )

    def _refresh_source_extracted_indicators(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Refresh source thumbnail borders after output-dir or extraction changes."""
        for path, widget in self.source_path_to_widget.items():
            label = widget.findChild(ClickableLabel)
            if label:
                self._update_source_label_style(
                    path, label, path == getattr(self, "video_path", None)
                )

    def scan_directory(self: "VideoExtractorSubTabHostProtocol", path: str):
        if not os.path.isdir(path):
            return

        # Refuse to start while Qt Multimedia's startup device probe may
        # still be in flight (issue #81 root cause #8) -- see
        # startup_probe_guard.py and
        # .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md.
        _remaining_ms = startup_settle_remaining_ms()
        print(
            f"[startup-probe-guard] ExtractorTab.scan_directory({path!r}): "
            f"remaining_ms={_remaining_ms}",
            flush=True,
        )
        telemetry.emit(
            "thread-lifecycle", "extractor_scan_directory.enter",
            panel=id(self), directory=path, remaining_ms=_remaining_ms,
        )
        if _remaining_ms > 0:
            QTimer.singleShot(_remaining_ms, lambda: self.scan_directory(path))
            return

        normalized = os.path.normpath(path)
        current_source = (
            os.path.normpath(self.line_edit_dir.text())
            if self.line_edit_dir.text()
            else ""
        )
        extraction_path = (
            os.path.normpath(str(self.extraction_dir))
            if getattr(self, "extraction_dir", None)
            else ""
        )
        if (
            extraction_path
            and normalized == extraction_path
            and current_source
            and current_source != extraction_path
        ):
            return

        self.line_edit_dir.setText(path)
        self.last_browsed_scan_dir = path
        self._save_last_dir(path)

        # Bump BEFORE any teardown/dispatch below so a still-in-flight
        # BatchVideoLoaderWorker result from a previous scan_directory()
        # call is unambiguously identifiable as stale by the time it's
        # delivered (see this module's docstring).
        self._extractor_scan_generation = getattr(self, "_extractor_scan_generation", 0) + 1

        # Clear grid and path tracking
        paths_to_remove = list(self.source_path_to_widget.keys())
        for p in paths_to_remove:
            widget = self.source_path_to_widget.pop(p)
            widget.deleteLater()

        while self.source_grid.count():
            item = self.source_grid.takeAt(0)
            item_widget = item.widget()
            if item_widget:
                item_widget.deleteLater()

        # 0. Refresh extracted stems cache
        self._refresh_extracted_stems_cache()

        # 1. Plain synchronous directory listing -- no background worker.
        try:
            entries = sorted(os.scandir(path), key=lambda e: natural_sort_key(e.name))
            video_paths = [
                e.path
                for e in entries
                if e.is_file()
                and Path(e.path).suffix.lower() in SUPPORTED_VIDEO_FORMATS
            ]
        except Exception:
            video_paths = []

        # 2. Populate grid with placeholders in alphabetical order. Limit
        # to MAX_PREVIEW_ITEMS to avoid OOM/crash if the directory is
        # massive. Thumbnails are shown only when a disk cache entry
        # already exists from a prior session (_get_disk_cache_path) --
        # nothing generates a *new* thumbnail here anymore.
        video_paths_limited = video_paths[:MAX_PREVIEW_ITEMS]

        paths_needing_thumbnail = []
        for i, v_path in enumerate(video_paths_limited):
            cached_image = self._initial_pixmap_cache.get(v_path)
            if cached_image is None:
                disk_cache = self._get_disk_cache_path(v_path)
                if os.path.exists(disk_cache):
                    img = QImage(disk_cache)
                    if not img.isNull():
                        cached_image = img
                        self._initial_pixmap_cache[v_path] = img

            widget = self._create_source_placeholder_widget(v_path)
            self.source_path_to_widget[v_path] = widget
            row = i // 12
            col = i % 12
            self.source_grid.addWidget(widget, row, col)

            if cached_image:
                self.add_source_thumbnail(v_path, cached_image)
            else:
                paths_needing_thumbnail.append(v_path)

        # 3. Generate thumbnails for entries with no disk-cache hit, via
        # QThreadPool (BatchVideoLoaderWorker) -- see this module's
        # docstring for why this replaces the old VideoScannerWorker.
        if paths_needing_thumbnail:
            _generation = self._extractor_scan_generation
            worker = BatchVideoLoaderWorker(paths_needing_thumbnail, 120, crop_square=True)
            worker.signals.result.connect(
                lambda p, img, _gen=_generation: self._on_source_video_thumbnail(p, img, _gen)
            )
            worker.signals.batch_result.connect(
                lambda results, paths, _gen=_generation: self._on_source_scan_batch_finished(_gen)
            )
            telemetry.emit(
                "thread-lifecycle", "extractor_batch_video_worker.start",
                panel=id(self), directory=path, count=len(paths_needing_thumbnail),
            )
            self.operation_thread_pool.start(worker)
        else:
            self.scan_progress_complete()

    def _on_source_video_thumbnail(self: "VideoExtractorSubTabHostProtocol", path: str, image: QImage, generation: int) -> None:
        # Directory switched again since this batch was dispatched --
        # source_path_to_widget now belongs to a different scan entirely.
        if generation != getattr(self, "_extractor_scan_generation", None):
            return
        if image and not image.isNull():
            self.add_source_thumbnail(path, image)

    def _on_source_scan_batch_finished(self: "VideoExtractorSubTabHostProtocol", generation: int) -> None:
        if generation != getattr(self, "_extractor_scan_generation", None):
            return
        self.scan_progress_complete()

    def _create_source_placeholder_widget(self: "VideoExtractorSubTabHostProtocol", path: str) -> QWidget:
        """Creates a placeholder widget with 'Loading...' state for the source gallery."""
        thumb_size = 120
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)

        clickable_label = ClickableLabel(file_path=path)
        clickable_label.setFixedSize(thumb_size, thumb_size)
        clickable_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clickable_label.setText("Loading...")
        clickable_label.setStyleSheet(
            "border: 1px dashed #666; color: #888; font-size: 10px;"
        )

        clickable_label.path_clicked.connect(self.load_media)
        clickable_label.path_right_clicked.connect(self.show_source_context_menu)

        self._update_source_label_style(
            path, clickable_label, getattr(self, "video_path", None) == path
        )

        layout.addWidget(clickable_label)

        # File Name Label (Alphabetical position preserved here)
        file_name = Path(path).name
        name_label = QLabel(file_name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setFixedWidth(thumb_size)
        fm = name_label.fontMetrics()
        elided_text = fm.elidedText(
            file_name, Qt.TextElideMode.ElideMiddle, thumb_size - 8
        )
        name_label.setText(elided_text)
        name_label.setToolTip(file_name)
        name_label.setStyleSheet(
            "color: #bbb; font-size: 10px; border: none; padding-top: 2px;"
        )

        layout.addWidget(name_label)
        return container

    def scan_progress_complete(self: "VideoExtractorSubTabHostProtocol"):
        pass

    @Slot(str, object)
    def add_source_thumbnail(self: "VideoExtractorSubTabHostProtocol", path: str, image_or_pixmap: Any):
        """Updates an existing alphabetical placeholder with a thumbnail
        image, whether from disk cache or freshly generated by
        BatchVideoLoaderWorker (see scan_directory())."""
        # 1. Resolve to Pixmap
        if isinstance(image_or_pixmap, QPixmap):
            pixmap = image_or_pixmap
        elif isinstance(image_or_pixmap, QImage):
            pixmap = QPixmap.fromImage(image_or_pixmap)
        else:
            pixmap = QPixmap()

        # 1.5. Cache to memory if successful
        if not pixmap.isNull() and path not in self._initial_pixmap_cache:
            if isinstance(image_or_pixmap, QImage):
                self._initial_pixmap_cache[path] = image_or_pixmap
            elif isinstance(image_or_pixmap, QPixmap):
                self._initial_pixmap_cache[path] = image_or_pixmap.toImage()

        # 2. Find and update the existing widget
        container = self.source_path_to_widget.get(path)
        if not container:
            return

        clickable_label = container.findChild(ClickableLabel)
        if not clickable_label:
            return

        if not pixmap.isNull():
            clickable_label.setPixmap(pixmap)
            clickable_label.setText("")  # Remove "Loading..." text
        else:
            # No thumbnail available (generation failed or is still in
            # flight -- gets called again by _on_source_video_thumbnail
            # once the BatchVideoLoaderWorker result arrives).
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                clickable_label.setText("VIDEO")
            else:
                clickable_label.setText("No Preview")

        self._update_source_label_style(
            path, clickable_label, getattr(self, "video_path", None) == path
        )

    @Slot(QPoint, str)
    def show_source_context_menu(self: "VideoExtractorSubTabHostProtocol", global_pos: QPoint, path: str):
        menu = QMenu(cast(QWidget, self))

        is_open = False
        tab_idx = -1
        for i in range(self.active_videos_tabbar.count()):
            if self.active_videos_tabbar.tabData(i) == path:
                is_open = True
                tab_idx = i
                break

        if is_open:
            close_action = QAction("Close Video", cast(QWidget, self))
            close_action.triggered.connect(
                lambda: self._on_active_video_tab_closed(tab_idx)
            )
            menu.addAction(close_action)
        else:
            open_action = QAction("Open Video", cast(QWidget, self))
            open_action.triggered.connect(lambda: self.load_media(path))
            menu.addAction(open_action)

        view_action = QAction("View Preview", cast(QWidget, self))
        view_action.triggered.connect(lambda: self.handle_thumbnail_double_click(path))
        menu.addAction(view_action)

        menu.exec(global_pos)

    @Slot(QPoint)
    def _show_tab_context_menu(self: "VideoExtractorSubTabHostProtocol", pos: QPoint):
        idx = self.active_videos_tabbar.tabAt(pos)
        if idx >= 0:
            menu = QMenu(cast(QWidget, self))
            close_action = QAction("Close Video", cast(QWidget, self))
            close_action.triggered.connect(
                lambda: self._on_active_video_tab_closed(idx)
            )
            menu.addAction(close_action)
            menu.exec(self.active_videos_tabbar.mapToGlobal(pos))

    def _refresh_extracted_stems_cache(self: "VideoExtractorSubTabHostProtocol"):
        """Scans extraction_dir once and caches which video stems have files."""
        self._extracted_stems_cache.clear()
        if not self.extraction_dir.exists():
            return

        # Regex to extract stem from all known extraction outputs:
        # {stem}_{ms}ms.png, {stem}_{ms}ms_{i}.png, {stem}_smart_{ms}ms.png,
        # {stem}_smart_{ms}ms_{temp_id}.png, {stem}_snap_{ms}ms.png,
        # {stem}_{start}ms_{end}ms.gif, {stem}_{start}ms_{end}ms.mp4
        pattern = re.compile(
            r"^(?P<stem>.+?)_("
            r"\d+ms|"
            r"\d+ms_\d+|"
            r"smart_\d+ms|"
            r"smart_\d+ms_\d+|"
            r"snap_\d+ms|"
            r"\d+ms_\d+ms"
            r")\.(png|gif|mp4)$"
        )
        try:
            for entry in os.scandir(self.extraction_dir):
                if entry.is_file():
                    match = pattern.match(entry.name)
                    if match:
                        stem = match.group("stem")
                        self._extracted_stems_cache.add(stem)
        except Exception as e:
            print(f"Error refreshing extracted stems cache: {e}")

    def _has_extracted_files(self: "VideoExtractorSubTabHostProtocol", video_path: str) -> bool:
        """Check if the video has extracted files in the output directory using cache."""
        if not self._extracted_stems_cache:
            self._refresh_extracted_stems_cache()

        stem = Path(video_path).stem
        return stem in self._extracted_stems_cache

    def _update_source_label_style(
        self: "VideoExtractorSubTabHostProtocol", path: str, label: ClickableLabel, selected: bool
    ):
        has_extracted = self._has_extracted_files(path)
        is_other_open = (
            hasattr(self, "active_videos_config")
            and path in self.active_videos_config
            and path != self.video_path
        )

        if selected:
            label.setStyleSheet("border: 3px solid #3498db; border-radius: 4px;")
        elif is_other_open:
            if label.text() == "VIDEO":
                label.setStyleSheet(
                    "border: 2px solid #9b59b6; color: #9b59b6; font-weight: bold;  border-radius: 4px;"
                )
            elif label.text() == "No Preview" or label.text() == "Loading...":
                label.setStyleSheet(
                    "border: 2px solid #9b59b6; color: #9b59b6; border-radius: 4px;"
                )
            else:
                label.setStyleSheet("border: 2px solid #9b59b6; border-radius: 4px;")
        else:
            if label.text() == "VIDEO":
                if has_extracted:
                    label.setStyleSheet(
                        "border: 2px solid #2ecc71; color: #2ecc71; font-weight: bold;  border-radius: 4px;"
                    )
                else:
                    label.setStyleSheet(
                        "border: 2px solid #3498db; color: #3498db; font-weight: bold;  border-radius: 4px;"
                    )
            elif label.text() == "No Preview":
                label.setStyleSheet(
                    "border: 1px dashed #666; color: #888; border-radius: 4px;"
                )
            elif label.text() == "Loading...":
                label.setStyleSheet(
                    "border: 1px dashed #666; color: #888; font-size: 10px; border-radius: 4px;"
                )
            else:
                if has_extracted:
                    label.setStyleSheet(
                        "border: 2px solid #2ecc71; border-radius: 4px;"
                    )
                else:
                    label.setStyleSheet(
                        "border: 2px solid #4f545c; border-radius: 4px;"
                    )


__all__ = ["_DirectoryScanningMixin"]
