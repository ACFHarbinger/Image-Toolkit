"""Merge run/cancel + result confirm dialog (save/copy/export/discard) for ``MergeTab``.

Extracted from ``merge_tab.py`` -- pure code motion, no logic change
(see ``_ui_config.py``'s docstring).
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Dict, Optional

import cv2
from PIL import Image as PILImage
from PySide6.QtCore import Q_ARG, QEventLoop, QMetaObject, Qt, Slot
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from ....components import ScrollVideoExportDialog
from ....helpers import MergeWorker, ScrollVideoExportWorker
from ....windows import ImagePreviewWindow


class _MergeExecutionMixin:
    """Run/cancel the merge worker and drive the post-merge result dialog."""

    def keyPressEvent(self, event: QKeyEvent):
        """Dispatch Merge-tab shortcuts before gallery navigation."""
        from ....utils.manager.shortcut_manager import get_registry

        reg = get_registry()
        if reg.matches(event, "merge.run"):
            self.start_merge()
            event.accept()
            return
        if reg.matches(event, "merge.cancel"):
            self.cancel_merge()
            event.accept()
            return
        super().keyPressEvent(event)  # type: ignore[misc,safe-super]

    # ─── Helper: UI reset ───────────────────────────────────────────────────────

    def reset_ui_state(self):
        self.cancel_button.setVisible(False)
        self.run_button.setVisible(True)
        self.run_button.setEnabled(True)
        self.current_merge_worker = None
        self.current_merge_thread = None
        self.on_selection_changed()

    # ─── Cancel Merge ───────────────────────────────────────────────────────────

    def cleanup_merge_worker(self):
        worker = self.current_merge_worker
        self.current_merge_worker = None
        self.current_merge_thread = None
        if worker is not None:
            try:
                worker.sig_finished.disconnect()
                worker.error.disconnect()
                worker.progress.disconnect()
            except Exception:
                pass
            worker.cancel()
            worker.requestInterruption()
            worker.quit()
            self._track_and_cleanup_thread(worker)

    @Slot()
    def cancel_merge(self):
        self.status_label.setText("Cancelling…")
        worker = self.current_merge_worker
        if worker:
            worker.cancel()
            worker.requestInterruption()
        self.cleanup_merge_worker()
        self.cleanup_temp_file()
        self.status_label.setText("Merge cancelled.")
        self.reset_ui_state()

    @Slot()
    def _cleanup_zombie_thread(self):
        pass

    # ─── Merge ──────────────────────────────────────────────────────────────────

    def start_merge(self):
        if len(self.selected_files) < 2:
            QMessageBox.warning(self, "Invalid", "Select at least 2 images.")
            return

        direction = self.direction.currentText()
        ext = ".gif" if direction == "gif" else ".png"
        temp_dir = tempfile.gettempdir()
        temp_filename = next(tempfile._get_candidate_names()) + ext  # pyrefly: ignore [missing-attribute]
        target_path = os.path.join(temp_dir, temp_filename)
        self.temp_file_path = target_path

        self.pending_save_path = None
        if self.output_dir and os.path.isdir(self.output_dir):
            filename = self.output_filename_input.text().strip()
            if not filename:
                filename = next(tempfile._get_candidate_names())  # pyrefly: ignore [missing-attribute]
            if not filename.lower().endswith(ext):
                filename += ext
            self.pending_save_path = os.path.join(self.output_dir, filename)

        merge_config = self.collect(self.temp_file_path)

        self.run_button.setVisible(False)
        self.cancel_button.setVisible(True)
        self.status_label.setText("Merging…")

        if cv2.ocl.haveOpenCL():
            cv2.ocl.finish()

        worker = MergeWorker(merge_config)
        self.current_merge_worker = worker
        self.current_merge_thread = worker

        worker.progress.connect(
            lambda c, t: self.status_label.setText(f"Merging {c}/{t}")
        )

        worker.error.connect(self.on_merge_error)

        def invoke_cleanup(path):
            # pyrefly: ignore [no-matching-overload]
            QMetaObject.invokeMethod(
                self,
                "_cleanup_merge_worker_and_show_dialog",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, path),
            )

        worker.sig_finished.connect(invoke_cleanup)
        worker.start()

    @Slot(str)
    def _cleanup_merge_worker_and_show_dialog(self, result_path: str):
        self.cleanup_merge_worker()
        self.reset_ui_state()
        self.show_preview_and_confirm(result_path)

    def on_merge_error(self, msg: str):
        self.cleanup_merge_worker()
        self.cleanup_temp_file()
        self.on_selection_changed()
        self.reset_ui_state()
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)

    @Slot(str)
    def show_preview_and_confirm(self, result_path: str):
        if not os.path.exists(result_path):
            self.on_merge_error(f"Failed to create merge file at: {result_path}")
            return

        self.status_label.setText("Merge complete.")
        self._last_merged_pixmap = QPixmap(result_path)

        preview_window = ImagePreviewWindow(
            image_path=result_path,
            db_tab_ref=None,
            parent=self,
            all_paths=[result_path],
            start_index=0,
        )
        preview_window.setWindowTitle("Merged Image Preview")
        preview_window.show()
        preview_window.activateWindow()

        confirm = QMessageBox(self)
        confirm.setWindowTitle("Save Merged Image?")

        if self.pending_save_path:
            confirm.setText(
                f"Merge successful. Save to configured output?\n\n{self.pending_save_path}"
            )
            save_text = "Save"
        else:
            confirm.setText("Merge successful. Choose an action:")
            save_text = "Save As…"

        copy_btn = confirm.addButton(
            "Copy to Clipboard", QMessageBox.ButtonRole.ActionRole
        )
        export_video_btn = confirm.addButton(
            "Export as Video…", QMessageBox.ButtonRole.ActionRole
        )
        save_btn = confirm.addButton(save_text, QMessageBox.ButtonRole.AcceptRole)
        save_add_btn = confirm.addButton(
            "Save and Add to Canvas", QMessageBox.ButtonRole.AcceptRole
        )
        confirm.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        confirm.addButton(QMessageBox.StandardButton.Cancel)
        confirm.exec()
        clicked = confirm.clickedButton()

        saved_final_path = None

        if clicked == export_video_btn:
            # Doesn't consume result_path — re-show the same confirm dialog
            # afterwards so the user can still Save/Copy/Discard the image.
            self._export_result_as_video(result_path)
            preview_window.close()
            self.show_preview_and_confirm(result_path)
            return

        if clicked == copy_btn:
            if self._last_merged_pixmap:
                QApplication.clipboard().setPixmap(self._last_merged_pixmap)
            self.cleanup_temp_file()

        elif clicked in (save_btn, save_add_btn):
            if self.pending_save_path:
                try:
                    if os.path.exists(self.pending_save_path):
                        overwrite = QMessageBox.question(
                            self,
                            "Overwrite?",
                            f"File already exists:\n{self.pending_save_path}\nOverwrite?",
                            QMessageBox.StandardButton.Yes
                            | QMessageBox.StandardButton.No,
                        )
                        if overwrite != QMessageBox.StandardButton.Yes:
                            self.cleanup_temp_file()
                            return
                    shutil.move(result_path, self.pending_save_path)
                    saved_final_path = self.pending_save_path
                    self.temp_file_path = None
                    self.last_output_dir = os.path.dirname(saved_final_path)
                    QMessageBox.information(
                        self, "Success", f"Saved to {saved_final_path}"
                    )
                except Exception as e:
                    QMessageBox.critical(
                        self, "Save Error", f"Failed to move file: {e}"
                    )
                    self.cleanup_temp_file()
            else:
                filter_str = (
                    "GIF (*.gif)"
                    if result_path.lower().endswith(".gif")
                    else "PNG (*.png)"
                )
                start_dir = (
                    self.last_output_dir
                    if self.last_output_dir
                    else self.last_browsed_scan_dir
                )
                out, _ = QFileDialog.getSaveFileName(
                    self, "Save Merged Image", start_dir, filter_str
                )
                if out:
                    try:
                        shutil.move(result_path, out)
                        saved_final_path = out
                        self.temp_file_path = None
                        self.last_output_dir = os.path.dirname(out)
                        QMessageBox.information(self, "Success", f"Saved to {out}")
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Move failed: {e}")
                        self.cleanup_temp_file()
                else:
                    self.cleanup_temp_file()

            if saved_final_path and clicked == save_add_btn:
                self._inject_new_image(saved_final_path)
        else:
            self.cleanup_temp_file()

        self._last_merged_pixmap = None
        if self.temp_file_path is None and not os.path.exists(result_path):
            preview_window.close()

        self.status_label.setText("Ready to merge.")

    def _export_result_as_video(self, result_path: str):
        """
        Roadmap §4.2 — Export Stitched Panorama to Scrolling Video (Option
        B: FFmpeg pipe). Triggered from the "Export as Video…" action in the
        merge-result confirm dialog; does not consume/move result_path so
        the normal Save/Copy/Discard flow still applies afterwards.
        """
        try:
            with PILImage.open(result_path) as im:
                img_size = im.size
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read merged image: {e}")
            return

        dialog = ScrollVideoExportDialog(img_size, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        params = dialog.get_values()

        start_dir = (
            self.last_output_dir if self.last_output_dir else self.last_browsed_scan_dir
        )
        default_name = os.path.splitext(os.path.basename(result_path))[0] + "_scroll.mp4"
        start_path = os.path.join(start_dir, default_name) if start_dir else default_name

        # DontUseNativeDialog is mandatory in this app: the native GTK
        # dialog + the live JVM is a known SIGSEGV (see CLAUDE memory).
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Scrolling Video",
            start_path,
            "MP4 Video (*.mp4)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not out_path:
            return
        if not out_path.lower().endswith(".mp4"):
            out_path += ".mp4"

        self.status_label.setText("Exporting scrolling video…")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        worker = ScrollVideoExportWorker(
            result_path,
            out_path,
            scroll_speed_px_per_frame=params["scroll_speed_px_per_frame"],
            fps=params["fps"],
            resolution=params["resolution"],
            codec=params["codec"],
        )

        loop = QEventLoop()
        outcome: Dict[str, Optional[str]] = {"path": None, "error": None}

        def on_finished(path: str):
            outcome["path"] = path
            loop.quit()

        def on_error(msg: str):
            outcome["error"] = msg
            loop.quit()

        worker.sig_finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.start()
        loop.exec()
        worker.wait()

        QApplication.restoreOverrideCursor()
        self.status_label.setText("Ready to merge.")

        if outcome["error"]:
            QMessageBox.critical(self, "Export Failed", outcome["error"])
        else:
            QMessageBox.information(
                self,
                "Export Complete",
                f"Scrolling video saved to:\n{outcome['path']}",
            )

    def _inject_new_image(self, path: str):
        """Add a newly-saved merged image to the gallery and selection queue."""
        self.start_loading_gallery([path], append=True)
        self.selected_files.append(path)
        if self.direction.currentText() == "canvas":
            self.canvas_widget.add_image(path, QPixmap(path))
        else:
            self._refresh_queue_gallery()
        self.on_selection_changed()

    def cleanup_temp_file(self):
        if self.temp_file_path and os.path.exists(self.temp_file_path):
            try:
                os.remove(self.temp_file_path)
            except Exception as e:
                print(f"Error cleaning up temp file: {e}")
        self.temp_file_path = None


__all__ = ["_MergeExecutionMixin"]
