"""Worker lifecycle cleanup + QML-facing slots for ``MergeTab``.

Extracted from ``merge_tab.py`` -- pure code motion, no logic change
(see ``_ui_config.py``'s docstring).
"""

from __future__ import annotations

import contextlib
import os

from PySide6.QtCore import QEvent, Qt, Slot
from PySide6.QtWidgets import QFileDialog


class _LifecycleQmlMixin:
    """Cancel-on-close cleanup and the QML bridge slots."""

    def cancel_loading(self):
        if self.current_scan_worker:
            with contextlib.suppress(Exception):
                self.current_scan_worker.scan_finished.disconnect()
            with contextlib.suppress(Exception):
                self.current_scan_worker.stop()
                self.current_scan_worker.requestInterruption()
                self.current_scan_worker.quit()
                self.current_scan_worker.wait()
            self.current_scan_worker = None
            self.current_scan_thread = None

        if self.current_merge_worker:
            with contextlib.suppress(Exception):
                self.current_merge_worker.cancel()
                self.current_merge_worker.requestInterruption()
                self.current_merge_worker.quit()
                self.current_merge_worker.wait()
            self.current_merge_worker = None
            self.current_merge_thread = None

        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()

        super().cancel_loading()

    def closeEvent(self, event):
        self.cancel_loading()
        super().closeEvent(event)

    # ─── QML handlers ───────────────────────────────────────────────────────────

    @Slot(str)
    def browse_input_qml(self, current_path: str = ""):
        starting_dir = (
            current_path if os.path.isdir(current_path) else self.last_browsed_scan_dir
        )
        d = QFileDialog.getExistingDirectory(
            self, "Select Directory to Scan", starting_dir
        )
        if d:
            self.scan_directory_path.setText(d)
            self.last_browsed_scan_dir = d
            self.qml_input_path_changed.emit(d)
            self.populate_scan_gallery(d)
            return d
        return ""

    @Slot(str, int, int, str)
    def start_merge_qml(
        self, direction: str, spacing: int, duration: int, align_mode: str
    ):
        self.direction.setCurrentText(direction)
        self.spacing.setValue(spacing)
        self.duration_spin.setValue(duration)
        self.align_mode.setCurrentText(align_mode)
        self.start_merge()

    @Slot(list)
    def set_selected_files_qml(self, paths):
        self.selected_files = list(paths)
        if self.direction.currentText() != "canvas":
            self._refresh_queue_gallery()
        self.on_selection_changed()

    def eventFilter(self, watched, event):
        if (
            (watched == getattr(self, "page_scroll", None) or
             (hasattr(self, "page_scroll") and watched == self.page_scroll.viewport()))
            and event.type() == QEvent.Type.Wheel
            and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        ):
            return True
        return super().eventFilter(watched, event)


__all__ = ["_LifecycleQmlMixin"]
