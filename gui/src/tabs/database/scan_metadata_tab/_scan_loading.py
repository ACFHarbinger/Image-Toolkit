"""Scan-directory browsing, worker thread lifecycle, and page-load orchestration.

Extracted from ``scan_metadata_tab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer, Slot
from PySide6.QtWidgets import QFileDialog

from gui.src.constants.ui import DIALOG_OPTS
from gui.src.helpers import ImageScannerWorker

from ....utils.sort_utils import natural_sort_key


class _ScanLoadingMixin:
    """Browse/scan the input directory, manage the scanner thread, and apply filters."""

    # --- THREAD SAFETY CLEANUP METHOD ---
    def _stop_running_threads(self):
        """Safely interrupts and cleans up any active scanner or loader threads."""
        self._loading_cancelled = True

        if self.scan_thread and self.scan_thread.isRunning():
            with contextlib.suppress(Exception):
                if self.scan_worker:
                    self.scan_worker.scan_finished.disconnect()
                    self.scan_worker.scan_error.disconnect()
            self.scan_thread.requestInterruption()
            self.scan_thread.quit()
            self.scan_thread.wait()
            self.scan_worker = None
            self.scan_thread = None

        # Clear the ThreadPool
        if hasattr(self, "thread_pool"):
            self.thread_pool.clear()
            self.thread_pool.waitForDone(-1)

        # Dialog removed, so no close logic needed here

    def cancel_loading(self):
        """Slot for cancelling operation."""
        with contextlib.suppress(Exception):
            super().cancel_loading()
        if hasattr(self, "dual"):
            self.dual.cancel_loading()
        self._stop_running_threads()
        self._loaded_results_buffer.clear()
        print("Loading cancelled by user.")

    def handle_scan_directory_return(self):
        directory = self.scan_directory_path.text().strip()
        if directory and Path(directory).is_dir():
            self.populate_scan_image_gallery(directory)
        else:
            self.browse_scan_directory()

    def browse_scan_directory(self):
        start_dir = self.last_browsed_scan_dir
        options = (
            DIALOG_OPTS
            | QFileDialog.Option.ShowDirsOnly
            | QFileDialog.Option.DontResolveSymlinks
        )
        directory = QFileDialog.getExistingDirectory(
            self, "Select directory to scan", start_dir, options
        )
        if directory:
            self.last_browsed_scan_dir = directory
            self.scan_directory_path.setText(directory)
            self.populate_scan_image_gallery(directory)

    def populate_scan_image_gallery(self, directory: str, is_refresh: bool = False):
        self.scanned_dir = directory

        # Stop all running threads before starting a new scan/load
        self._stop_running_threads()
        self._loading_cancelled = False

        if not is_refresh or not self.scan_image_list:
            self.dual.clear()
            self.scan_image_list = []
            self.scan_filtered_list = []  # Reset filtered list
            self.selected_image_paths = set()

            loop = QEventLoop()
            QTimer.singleShot(1, loop.quit)
            loop.exec()

            self.scan_worker = ImageScannerWorker(directory)
            self.scan_thread = self.scan_worker

            self.scan_worker.scan_finished.connect(self.process_scan_results)
            self.scan_worker.scan_error.connect(self.handle_scan_error)

            self.scan_worker.finished.connect(self.on_scan_thread_finished)
            self.scan_worker.finished.connect(self.scan_worker.deleteLater)

            self.scan_worker.start()
            return

        # If performing a refresh (toggling view_new_only), re-apply filters to existing list
        self.apply_scan_filters()

    # --- QML Wrappers ---
    def start_scan(self):
        """Wrapper for QML to start scanning using current text field value."""
        self.handle_scan_directory_return()

    def stop_scan(self):
        """Wrapper for QML to stop scanning."""
        self.cancel_loading()

    def upsert_selected(self):
        """Wrapper for QML to upsert selected images."""
        self.perform_upsert_operation()

    @Slot()
    def on_scan_thread_finished(self):
        self.scan_thread = None
        self.scan_worker = None

    @Slot(list)
    def process_scan_results(self, image_paths: list[str]):
        if self._loading_cancelled:
            return
        self.scan_image_list = image_paths
        self.apply_scan_filters()

    def apply_scan_filters(self):
        """Filters the raw scan list based on settings (Show New Only) and feeds
        the virtual found gallery."""
        self.scan_filtered_list = sorted(
            self.scan_image_list, key=natural_sort_key
        )  # Sort by default

        # FILTERING LOGIC
        if self.database_service.db is not None:
            if self.view_new_only:
                db = self.database_service.db
                paths_not_in_db = []
                for path in self.scan_image_list:
                    if not db.get_image_by_path(path):
                        paths_not_in_db.append(path)
                self.scan_filtered_list = sorted(paths_not_in_db, key=natural_sort_key)

            elif self.view_in_db_only:
                db = self.database_service.db
                paths_in_db = []
                for path in self.scan_image_list:
                    if db.get_image_by_path(path):
                        paths_in_db.append(path)
                self.scan_filtered_list = sorted(paths_in_db, key=natural_sort_key)

        self._load_current_scan_page()

    def _load_current_scan_page(self):
        """Feed the current filtered scan list into the dual's found panel.

        The virtual gallery renders every filtered row with viewport culling
        (scroll prefetch replaces the old lazy-load-on-scroll), so the page
        slice / placeholder-card grid is gone."""
        self._refresh_scan_gallery()

    def _refresh_scan_gallery(self):
        """Rebuild the dual's found panel from ``scan_filtered_list`` and mark
        which rows already exist in the database (green border via the
        VirtualGalleryDelegate)."""
        self.dual.set_found_paths(self.scan_filtered_list)

        # Batch DB check for in-database styling
        db = self.database_service.db
        in_db = set()
        if db and self.scan_filtered_list:
            try:
                if hasattr(db, "paths_in_db"):
                    in_db = db.paths_in_db(self.scan_filtered_list)
                elif hasattr(db, "_images") and hasattr(db._images, "paths_in_db"):
                    in_db = db._images.paths_in_db(self.scan_filtered_list)
                else:
                    with db.conn.cursor() as cur:
                        cur.execute(
                            "SELECT file_path FROM images WHERE file_path = ANY(%s)",
                            (self.scan_filtered_list,),
                        )
                        in_db = {row[0] for row in cur.fetchall()}
            except Exception as e:
                print(f"Batch DB check error: {e}")
        self.dual.found_gallery.model.set_in_db(in_db)


__all__ = ["_ScanLoadingMixin"]
