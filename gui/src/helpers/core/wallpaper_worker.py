import time
import platform

if platform.system() == "Windows":
    import comtypes

from screeninfo import Monitor
from typing import Dict, List, Optional
from PySide6.QtCore import QObject, Signal, QRunnable, Slot
from backend.src.core import WallpaperManager


class WallpaperWorkerSignals(QObject):
    """
    Defines the signals available from a running WallpaperWorker.
    """

    # Signal emitted with status updates (str)
    status_update = Signal(str)

    # Signal emitted when work is finished (bool success, str message)
    work_finished = Signal(bool, str)


class InterruptedError(Exception):
    """Custom exception to indicate manual cancellation."""

    pass


class WallpaperWorker(QRunnable):
    """
    Worker thread to apply wallpaper using WallpaperManager.
    """

    def __init__(
        self,
        path_map: Dict[str, str],
        monitors: List[Monitor],
        qdbus: str,
        wallpaper_style: str = "Fill",
    ):
        super().__init__()
        if WallpaperManager is None:
            raise ImportError("WallpaperManager class could not be imported.")

        self.qdbus = qdbus
        self.path_map = path_map
        self.monitors = monitors
        self.wallpaper_style = wallpaper_style  # Store the selected style
        self.signals = WallpaperWorkerSignals()
        self.is_running = True

    def _log(self, message: str):
        """Emits a status update signal if the worker is still running."""
        if self.is_running:
            timestamp = time.strftime("[%H:%M:%S]")
            self.signals.status_update.emit(f"{timestamp} {message}")

    @Slot()
    def run(self):
        """
        Execute the worker's task: applying the wallpaper.
        Initializes and uninitializes the COM apartment if on Windows.
        """
        if not self.is_running:
            return

        self._log("Wallpaper set worker started...")
        success = False
        message = "Worker did not run."

        # Initialize COM on the worker thread if on Windows
        com_initialized = False
        if platform.system() == "Windows" and comtypes:
            try:
                # Prepare the current thread for COM (STA model)
                comtypes.CoInitialize()
                com_initialized = True
                self._log("Windows COM apartment initialized.")
            except Exception as e:
                self._log(f"Warning: Failed to initialize COM on worker thread: {e}")
                # Don't fail the worker yet, let the wallpaper manager handle it.

        try:
            # --- Main Task ---
            WallpaperManager.apply_wallpaper(
                self.path_map, self.monitors, self.wallpaper_style, self.qdbus
            )

            if not self.is_running:
                raise InterruptedError("Work manually cancelled.")

            success = True
            message = "Wallpaper applied successfully."

        except InterruptedError as e:
            success = False
            message = str(e)
            self._log(f"Warning: {message}")

        except Exception as e:
            success = False
            message = f"Critical error: {e}"
            self._log(f"ERROR: {message}")

        finally:
            # Uninitialize COM on the worker thread if it was initialized
            if com_initialized:
                comtypes.CoUninitialize()
                self._log("Windows COM apartment uninitialized.")

            if self.is_running:
                self._log(f"Worker finished. Success: {success}")
                # Emit final signal
                self.signals.work_finished.emit(success, message)

    def stop(self):
        """
        Signals the worker to stop.
        """
        if self.is_running:
            self.is_running = False
            self._log("Stop signal received. Worker will terminate.")
