"""Scan-directory browsing, worker thread lifecycle, and page-load orchestration.

Extracted from ``scan_metadata_tab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from pathlib import Path

from gui.src.helpers import ImageScannerWorker
from PySide6.QtCore import QEventLoop, Qt, QTimer, Slot
from PySide6.QtWidgets import QFileDialog

from ...utils.sort_utils import natural_sort_key


class _ScanLoadingMixin:
    """Browse/scan the input directory, manage the scanner thread, and apply filters."""

    # --- THREAD SAFETY CLEANUP METHOD ---
    def _stop_running_threads(self):
        """Safely interrupts and cleans up any active scanner or loader threads."""
        self._loading_cancelled = True

        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.requestInterruption()
            self.scan_thread.quit()
            self.scan_thread.wait(1000)
            self.scan_worker = None
            self.scan_thread = None

        # Clear the ThreadPool
        self.thread_pool.clear()

        # Dialog removed, so no close logic needed here

    def cancel_loading(self):
        """Slot for cancelling operation."""
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
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
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
            self.path_to_wrapper_map = {}
            self._clear_gallery(self.scan_thumbnail_layout)
            self._clear_gallery(self.selected_grid_layout)
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
        """Filters the raw scan list based on settings (Show New Only) and resets to Page 1."""
        self.scan_filtered_list = sorted(
            self.scan_image_list, key=natural_sort_key
        )  # Sort by default

        # FILTERING LOGIC
        if self.db_tab_ref.db is not None:
            if self.view_new_only:
                db = self.db_tab_ref.db
                paths_not_in_db = []
                for path in self.scan_image_list:
                    if not db.get_image_by_path(path):
                        paths_not_in_db.append(path)
                self.scan_filtered_list = sorted(paths_not_in_db, key=natural_sort_key)

            elif self.view_in_db_only:
                db = self.db_tab_ref.db
                paths_in_db = []
                for path in self.scan_image_list:
                    if db.get_image_by_path(path):
                        paths_in_db.append(path)
                self.scan_filtered_list = sorted(paths_in_db, key=natural_sort_key)

        # Reset to page 0 whenever filter changes or new scan happens
        self.scan_current_page = 0
        self._load_current_scan_page()

    def _load_current_scan_page(self):
        """Calculates the slice for the current page and initiates layout (images load lazily)."""

        # 1. Update Pagination UI
        self._update_pagination_ui(is_found=False, mode="scan")

        self._clear_gallery(self.scan_thumbnail_layout)
        self.path_to_wrapper_map.clear()

        # Reset Lazy Load State for new page
        self.loaded_paths.clear()
        self.loading_paths.clear()
        self.thread_pool.clear()

        if not self.scan_filtered_list:
            return

        # 2. Calculate Slice
        start_idx = self.scan_current_page * self.scan_page_size
        if self.scan_page_size == float("inf"):
            paths_to_load = self.scan_filtered_list
        else:
            end_idx = start_idx + self.scan_page_size
            paths_to_load = self.scan_filtered_list[start_idx:end_idx]

        # 3. Create Placeholders immediately
        columns = self._columns()

        # Batch DB Check
        db = self.db_tab_ref.db
        paths_in_db_set = set()
        if db:
            try:
                if paths_to_load:
                    if hasattr(db, "paths_in_db"):
                        paths_in_db_set = db.paths_in_db(paths_to_load)
                    elif hasattr(db, "_images") and hasattr(db._images, "paths_in_db"):
                        paths_in_db_set = db._images.paths_in_db(paths_to_load)
                    else:
                        with db.conn.cursor() as cur:
                            cur.execute(
                                "SELECT file_path FROM images WHERE file_path = ANY(%s)",
                                (paths_to_load,),
                            )
                            rows = cur.fetchall()
                            paths_in_db_set = {row[0] for row in rows}
            except Exception as e:
                print(f"Batch DB check error: {e}")

        # Populate Grid with Placeholders
        for index, path in enumerate(paths_to_load):
            row = index // columns
            col = index % columns

            is_in_db = path in paths_in_db_set
            is_selected = path in self.selected_image_paths

            # Create card with pixmap=None (Loading state)
            card = self._create_gallery_card(path, None, is_selected, is_in_db=is_in_db)

            card.path_clicked.connect(lambda checked, p=path: self.toggle_selection(p))
            card.path_double_clicked.connect(self._view_single_image_preview)
            card.path_right_clicked.connect(self.show_image_context_menu)

            self.scan_thumbnail_layout.addWidget(
                card, row, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            self.path_to_wrapper_map[path] = card

        self.scan_thumbnail_widget.adjustSize()

        # 4. Trigger Initial Lazy Load (Check what is visible immediately)
        # We give the layout a small moment to stabilize coordinates
        QTimer.singleShot(50, self._process_visible_items)


__all__ = ["_ScanLoadingMixin"]
