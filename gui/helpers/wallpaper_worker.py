import time

from typing import Dict, List
from screeninfo import Monitor
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
    def __init__(self, path_map: Dict[str, str], monitors: List[Monitor], wallpaper_style: str = "Fill"):
        super().__init__()
        if WallpaperManager is None:
            raise ImportError("WallpaperManager class could not be imported.")
            
        self.path_map = path_map
        self.monitors = monitors
        self.wallpaper_style = wallpaper_style # Store the selected style
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
        """
        if not self.is_running:
            return 
            
        self._log("Wallpaper set worker started...")
        success = False
        message = "Worker did not run."

        try:
            # --- Main Task ---
            # Pass the style to the core manager
            WallpaperManager.apply_wallpaper(self.path_map, self.monitors, self.wallpaper_style)
            
            if not self.is_running:
                # Check if stop() was called during the blocking call
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
