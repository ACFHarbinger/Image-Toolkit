import os
from typing import List, Optional, Tuple, Union

from backend.src.constants import HAS_NATIVE_IMAGING, SUPPORTED_IMG_FORMATS
from PySide6.QtCore import QObject, Signal, Slot

if HAS_NATIVE_IMAGING:
    import base


class ImageScannerWorker(QObject):
    """
    Worker to perform file system scanning on a separate thread.
    Optimized using os.scandir for faster directory traversal and
    skips hidden directories for efficiency.
    """

    scan_finished = Signal(list)
    scan_error = Signal(str)

    def __init__(self, directories: Union[str, List[str]], recursive: Optional[bool] = None):
        super().__init__()

        # Handle single string or list input
        if isinstance(directories, (str, os.PathLike)):
            self.directories = [directories]
        elif isinstance(directories, list):
            self.directories = [d for d in directories if d and os.path.isdir(d)]
        else:
            self.directories = []

        self.extensions: Tuple[str, ...] = tuple(
            f".{fmt.lower().lstrip('.')}" for fmt in SUPPORTED_IMG_FORMATS
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
        """
        Internal helper using os.scandir for performance.
        Returns a list of file paths found in this specific directory only.
        """
        found_images = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if self._is_cancelled or (
                        self.thread() and self.thread().isInterruptionRequested()
                    ):
                        return found_images

                    # Skip hidden files/directories
                    if entry.name.startswith("."):
                        continue

                    if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(self.extensions):
                        found_images.append(entry.path)
        except PermissionError:
            print(f"Permission denied: {path}")
        except OSError as e:
            print(f"OS Error scanning {path}: {e}")

        return found_images

    def _scan_recursive(self, path: str) -> List[str]:
        """
        Internal helper using os.scandir for performance.
        Returns a list of file paths found in this specific branch.
        """
        found_images = []
        try:
            # os.scandir is faster than os.walk as it uses cached DirEntry objects
            with os.scandir(path) as it:
                for entry in it:
                    if self._is_cancelled or (
                        self.thread() and self.thread().isInterruptionRequested()
                    ):
                        return found_images

                    # Skip hidden directories/files (starts with dot)
                    if entry.name.startswith("."):
                        continue

                    if entry.is_dir(follow_symlinks=False):
                        # Recursive call
                        found_images.extend(self._scan_recursive(entry.path))
                    elif entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(self.extensions):
                        found_images.append(entry.path)
        except PermissionError:
            # Log strictly to console or emit a non-breaking warning if desired
            # We skip this specific folder but return what we found so far
            print(f"Permission denied: {path}")
        except OSError as e:
            print(f"OS Error scanning {path}: {e}")

        return found_images

    @Slot()
    def run_scan(self):
        """
        Iterates through all provided directories and aggregates image paths.
        """
        all_image_paths = []

        if not self.directories:
            self.scan_error.emit("No valid directories provided for scanning.")
            return

        try:
            if HAS_NATIVE_IMAGING:
                # cpp-based parallel scan
                all_image_paths = base.scan_files_multi( # pyrefly: ignore [missing-attribute]
                    self.directories, list(self.extensions), self.recursive
                )
                if self._is_cancelled:
                    return
                self.scan_finished.emit(all_image_paths)
                return

            for directory in self.directories:
                if self._is_cancelled:
                    break
                if not os.path.isdir(directory):
                    self.scan_error.emit(f"Skipping invalid directory: {directory}")
                    continue  # Continue to next dir instead of aborting

                # Use the optimized scanner
                images_in_dir = self._scan_recursive(directory) if self.recursive else self._scan_flat(directory)
                all_image_paths.extend(images_in_dir)

            # Sort strictly at the end to minimize overhead
            self.scan_finished.emit(sorted(all_image_paths))

        except Exception as e:
            self.scan_error.emit(f"Critical error during scan: {e}")
