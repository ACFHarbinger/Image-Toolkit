import os
from typing import List, Optional, Tuple, Union

from backend.src.constants import HAS_NATIVE_IMAGING, SUPPORTED_VIDEO_FORMATS
from backend.src.core import telemetry
from PySide6.QtCore import QThread, Signal, Slot

from gui.src.helpers.gc_safe import gc_disabled_run

if HAS_NATIVE_IMAGING:
    import base


class VideoScannerWorker(QThread):
    """
    Worker to perform file system scanning (video paths only -- no
    thumbnail generation) on a separate thread. Deliberately modeled on
    ImageScannerWorker (gui/src/helpers/image/image_scan_worker.py), which
    was never implicated across 22+ rounds of the deleteOrphaned crash
    investigation (.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md).

    The original VideoScannerWorker combined scanning AND thumbnail
    generation in one QThread, fanning the latter out across an internal
    concurrent.futures.ThreadPoolExecutor -- concurrent subprocess+QImage
    decode work on threads Qt's own machinery doesn't manage. That
    thread/lifetime coupling is gone: this worker only lists file paths.
    Thumbnail generation is a separate concern, handled by
    VideoLoaderWorker/BatchVideoLoaderWorker on the normal QThreadPool,
    exactly like image thumbnails.
    """

    scan_finished = Signal(list)
    scan_error = Signal(str)

    def __init__(self, directories: Union[str, List[str]], recursive: Optional[bool] = None):
        super().__init__()

        if isinstance(directories, (str, os.PathLike)):
            self.directories = [directories]
        elif isinstance(directories, list):
            self.directories = [d for d in directories if d and os.path.isdir(d)]
        else:
            self.directories = []

        self.extensions: Tuple[str, ...] = tuple(
            f".{fmt.lower().lstrip('.')}" for fmt in SUPPORTED_VIDEO_FORMATS
        )
        self._is_cancelled = False

        if recursive is None:
            from gui.src.windows.settings.app_settings import AppSettings
            self.recursive = AppSettings.recursive_scan()
        else:
            self.recursive = recursive

    def stop(self):
        """Signals the worker to stop."""
        self._is_cancelled = True

    def _scan_flat(self, path: str) -> List[str]:
        found_videos = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if self._is_cancelled or self.isInterruptionRequested():
                        return found_videos
                    if entry.name.startswith("."):
                        continue
                    if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(self.extensions):
                        found_videos.append(entry.path)
        except PermissionError:
            print(f"Permission denied: {path}")
        except OSError as e:
            print(f"OS Error scanning {path}: {e}")

        return found_videos

    def _scan_recursive(self, path: str) -> List[str]:
        found_videos = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if self._is_cancelled or self.isInterruptionRequested():
                        return found_videos
                    if entry.name.startswith("."):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        found_videos.extend(self._scan_recursive(entry.path))
                    elif entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(self.extensions):
                        found_videos.append(entry.path)
        except PermissionError:
            print(f"Permission denied: {path}")
        except OSError as e:
            print(f"OS Error scanning {path}: {e}")

        return found_videos

    @Slot()
    def run_scan(self):
        """Iterates through all provided directories and aggregates video paths."""
        all_video_paths = []

        if not self.directories:
            self.scan_error.emit("No valid directories provided for scanning.")
            return

        try:
            if HAS_NATIVE_IMAGING:
                # Serialized against every other scanner worker's own call
                # into this same native boundary -- see
                # telemetry.NATIVE_SCAN_LOCK's docstring (image_scan_worker.py
                # takes the identical lock around its own call).
                with telemetry.span(
                    "native", "base.scan_files_multi",
                    directories=self.directories, recursive=self.recursive,
                ), telemetry.NATIVE_SCAN_LOCK:
                    all_video_paths = base.scan_files_multi(  # pyrefly: ignore [missing-attribute]
                        self.directories, list(self.extensions), self.recursive
                    )
                if self._is_cancelled:
                    return
                self.scan_finished.emit(all_video_paths)
                return

            for directory in self.directories:
                if self._is_cancelled:
                    break
                if not os.path.isdir(directory):
                    self.scan_error.emit(f"Skipping invalid directory: {directory}")
                    continue

                videos_in_dir = self._scan_recursive(directory) if self.recursive else self._scan_flat(directory)
                all_video_paths.extend(videos_in_dir)

            self.scan_finished.emit(sorted(all_video_paths))

        except Exception as e:
            self.scan_error.emit(f"Critical error during scan: {e}")

    @gc_disabled_run
    def run(self):
        self.run_scan()
