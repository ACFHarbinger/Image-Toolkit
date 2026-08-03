"""MediaLoaderWorker dispatch, cancellation, and completion handling.

Follows the same pattern as ``image_crawler_tab``'s ``_crawl_worker.py``.
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

from ....helpers import MediaLoaderWorker
from ._ui_builder import SOURCE_NHENTAI


class _DownloadWorkerMixin:
    """Starts/cancels the MediaLoaderWorker and handles the completion flow."""

    @Slot()
    def start_download(self):
        download_dir = self.download_dir_path.text().strip()
        if not download_dir:
            QMessageBox.warning(self, "Error", "Please select a download directory.")
            return

        if self.source_combo.currentIndex() == SOURCE_NHENTAI:
            gallery = self.nhentai_gallery_input.text().strip()
            if not gallery:
                QMessageBox.warning(self, "Error", "Please enter a gallery id or URL.")
                return
            source = "nhentai"
            config = {
                "gallery": gallery,
                "download_dir": download_dir,
            }
        else:
            reddit_source = self.reddit_source_input.text().strip()
            if not reddit_source:
                QMessageBox.warning(
                    self, "Error", "Please enter a subreddit, user, or post URL."
                )
                return
            source = "reddit"
            mode = {
                0: "subreddit",
                1: "user",
                2: "post",
            }[self.reddit_mode_combo.currentIndex()]
            config = {
                "source": reddit_source,
                "mode": mode,
                "sort": self.reddit_sort_combo.currentText(),
                "limit": self.reddit_limit_spin.value(),
                "download_images": self.reddit_download_images_chk.isChecked(),
                "download_videos": self.reddit_download_videos_chk.isChecked(),
                "download_dir": download_dir,
            }

        self.run_button.hide()
        self.cancel_button.show()
        self.progress_bar.show()
        self.status_label.setText(f"Starting {source} download...")

        self.worker = MediaLoaderWorker(source, config)
        self.worker.status.connect(self.status_label.setText)
        self.worker.media_saved.connect(self._on_media_saved)
        self.worker.sig_finished.connect(self._on_download_finished)
        self.worker.error.connect(self._on_download_error)
        self.worker.start()

    @Slot()
    def cancel_download(self):
        if self.worker is not None:
            self.worker.cancel()
            self.status_label.setText("Cancelling...")

    def _on_media_saved(self, path: str) -> None:
        self.saved_count = getattr(self, "saved_count", 0) + 1

    def _on_download_finished(self, count: int, message: str) -> None:
        self.run_button.show()
        self.cancel_button.hide()
        self.progress_bar.hide()
        self.status_label.setText(message)

    def _on_download_error(self, message: str) -> None:
        self.run_button.show()
        self.cancel_button.hide()
        self.progress_bar.hide()
        self.status_label.setText(message)
        QMessageBox.critical(self, "Error", message)


__all__ = ["_DownloadWorkerMixin"]
