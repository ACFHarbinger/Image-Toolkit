"""Crash-safe, incremental directory scanning for Wallpaper galleries.

Directory traversal runs in short GUI-event-loop slices. It creates no
``QThread``, worker ``QObject``, native scanner, or cross-thread signal. This
is intentional: repeated Wallpaper browsing had a long history of corrupting
Qt's event-dispatcher/socket-notifier bookkeeping while short-lived scanner
threads were being connected and destroyed.
"""

from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Deque, Iterator, Optional

from backend.src.constants import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS

from ......utils.sort_utils import natural_sort_key

if TYPE_CHECKING:
    from ....protos.wallpaper_common_base import WallpaperCommonBaseHostProtocol


_IMAGE_EXTENSIONS = tuple(f".{ext.lower().lstrip('.')}" for ext in SUPPORTED_IMG_FORMATS)
_VIDEO_EXTENSIONS = tuple(ext.lower() for ext in SUPPORTED_VIDEO_FORMATS)
_SCAN_SLICE_SECONDS = 0.004
_SCAN_SLICE_ENTRIES = 256


@dataclass
class _DirectoryScanState:
    generation: int
    directory: str
    emit_signal: bool
    recursive: bool
    pending_directories: Deque[str] = field(default_factory=deque)
    current_iterator: Optional[Iterator[os.DirEntry[str]]] = None
    image_paths: list[str] = field(default_factory=list)
    video_paths: list[str] = field(default_factory=list)

    def close_iterator(self) -> None:
        iterator = self.current_iterator
        self.current_iterator = None
        close = getattr(iterator, "close", None)
        if callable(close):
            close()


class _ScanPipelineMixin:
    """Incrementally enumerate one directory generation at a time."""

    gallery_image_paths: list[str]
    master_image_paths: list[str]

    def populate_scan_image_gallery(
        self: "WallpaperCommonBaseHostProtocol",
        directory: str,
        emit_signal: bool = True,
    ) -> None:
        if getattr(self, "background_type", None) == "Solid Color":
            return

        directory = os.path.abspath(os.path.expanduser(directory))
        self._directory_scan_generation += 1
        generation = self._directory_scan_generation

        # A new browse request supersedes the old generation immediately.
        # The scan iterator lives on this thread, so cancellation is just a
        # timer stop plus closing its directory descriptor; no worker teardown
        # or queued signal delivery is involved.
        self._cancel_directory_scan(invalidate=False)
        self._scan_pipeline_busy = True
        self._pending_scan_request = None

        # Drain the gallery generation before replacing paths. The legacy
        # scanner hook is defensive for instances surviving a source reload.
        self._stop_legacy_scanner_threads()
        self.scanned_dir = directory
        path_edit = getattr(self, "scan_directory_path", None)
        if path_edit is not None:
            path_edit.setText(directory)

        self.clear_gallery_widgets()
        self.path_to_label_map.clear()
        self.gallery_image_paths = []
        self.master_image_paths = []

        from gui.src.windows.settings.app_settings import AppSettings

        state = _DirectoryScanState(
            generation=generation,
            directory=directory,
            emit_signal=emit_signal,
            recursive=AppSettings.recursive_scan(),
        )
        state.pending_directories.append(directory)
        self._directory_scan_state = state
        self._directory_scan_timer.start(0)

    def _scan_directory_tick(  # noqa: C901 - bounded iterator state machine
        self: "WallpaperCommonBaseHostProtocol",
    ) -> None:
        state: Optional[_DirectoryScanState] = self._directory_scan_state
        if state is None or state.generation != self._directory_scan_generation:
            # The same timer also polls thumbnail settlement after enumeration.
            if getattr(self, "_scan_pipeline_busy", False):
                self._settle_scan_pipeline()
            return

        deadline = time.perf_counter() + _SCAN_SLICE_SECONDS
        processed = 0
        while processed < _SCAN_SLICE_ENTRIES and time.perf_counter() < deadline:
            if state.current_iterator is None:
                if not state.pending_directories:
                    self._finish_directory_scan(state)
                    return
                next_directory = state.pending_directories.popleft()
                try:
                    state.current_iterator = os.scandir(next_directory)
                except OSError:
                    continue

            try:
                entry = next(state.current_iterator)
            except StopIteration:
                state.close_iterator()
                continue
            except OSError:
                state.close_iterator()
                continue

            processed += 1
            if entry.name.startswith("."):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if state.recursive:
                        state.pending_directories.append(entry.path)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
            except OSError:
                continue

            lower_name = entry.name.lower()
            if lower_name.endswith(_IMAGE_EXTENSIONS):
                state.image_paths.append(entry.path)
            elif lower_name.endswith(_VIDEO_EXTENSIONS):
                state.video_paths.append(entry.path)

        self._directory_scan_timer.start(1)

    def _finish_directory_scan(
        self: "WallpaperCommonBaseHostProtocol", state: _DirectoryScanState
    ) -> None:
        if (
            state is not self._directory_scan_state
            or state.generation != self._directory_scan_generation
        ):
            state.close_iterator()
            return

        state.close_iterator()
        self._directory_scan_state = None
        paths = sorted(
            set(state.image_paths + state.video_paths), key=natural_sort_key
        )
        self.start_loading_gallery(paths, show_progress=False, append=False)
        self._emit_directory_scanned_on_settle = state.emit_signal
        self._settle_scan_pipeline()

    def _cancel_directory_scan(
        self: "WallpaperCommonBaseHostProtocol", *, invalidate: bool = True
    ) -> None:
        if invalidate:
            self._directory_scan_generation += 1
        self._directory_scan_timer.stop()
        state: Optional[_DirectoryScanState] = self._directory_scan_state
        self._directory_scan_state = None
        if state is not None:
            state.close_iterator()

    def _settle_scan_pipeline(self: "WallpaperCommonBaseHostProtocol") -> None:
        if self._directory_scan_state is not None:
            return

        gallery_model = getattr(getattr(self, "gallery", None), "model", None)
        has_pending = getattr(gallery_model, "has_pending_loads", None)
        if callable(has_pending) and has_pending():
            self._directory_scan_timer.start(25)
            return

        thread_pool = getattr(self, "thread_pool", None)
        if thread_pool is not None and thread_pool.activeThreadCount() > 0:
            self._directory_scan_timer.start(25)
            return

        self._scan_pipeline_busy = False
        should_mirror = getattr(self, "_emit_directory_scanned_on_settle", False)
        self._emit_directory_scanned_on_settle = False
        if should_mirror and self.scanned_dir:
            self.directory_scanned.emit(self.scanned_dir)

    def _scan_pipeline_watchdog(self: "WallpaperCommonBaseHostProtocol") -> None:
        """Compatibility hook retained for callers from older sessions."""
        self._settle_scan_pipeline()

    # Old queued connections may arrive after a source reload. Keeping these
    # slots as no-ops makes those deliveries harmless.
    def _on_image_scan_finished(
        self: "WallpaperCommonBaseHostProtocol", _paths: list, _worker: Any = None
    ) -> None:
        return

    def _on_video_scan_finished(
        self: "WallpaperCommonBaseHostProtocol", _paths: list, _worker: Any = None
    ) -> None:
        return

    def _on_video_scan_error(
        self: "WallpaperCommonBaseHostProtocol", _worker: Any = None
    ) -> None:
        return

    def _start_video_scan(
        self: "WallpaperCommonBaseHostProtocol", _directory: str
    ) -> None:
        return


__all__ = ["_ScanPipelineMixin"]
