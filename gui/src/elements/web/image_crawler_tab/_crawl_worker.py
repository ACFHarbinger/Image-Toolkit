"""ImageCrawlWorker dispatch, cancellation, and post-crawl pruning dialogs.

Extracted from ``image_crawler_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import contextlib
import os

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QDialog, QMessageBox

from ....helpers import ImageCrawlWorker


class _CrawlWorkerMixin:
    """Starts/cancels the ImageCrawlWorker and handles the completion flow."""

    @Slot()
    def start_crawl(self):  # noqa: C901
        # ... validation ...
        # Need to ensure QML knows we started
        self._is_crawling = True
        self.qml_crawling_changed.emit()
        self._log_output = "Starting crawl...\n"
        self.qml_log_changed.emit()

        download_dir = self.download_dir_path.text().strip()
        if not download_dir:
            QMessageBox.warning(self, "Error", "Please select a download directory.")
            return

        crawler_type_idx = self.crawler_type_combo.currentIndex()
        config = {"download_dir": download_dir}
        config["selection_mode"] = self.selection_mode_combo.currentText()

        if crawler_type_idx == 0:
            config["type"] = "general"
            config["url"] = self.url_input.text().strip()
            config["browser"] = self.browser_combo.currentText()
            config["headless"] = self.headless_checkbox.isChecked() # pyrefly: ignore [bad-assignment]
            config["screenshot_dir"] = self.screenshot_dir_path.text().strip() or None # pyrefly: ignore [bad-assignment]

            rep_str = self.replace_str_input.text().strip()
            reps = self.replacements_input.text().strip()
            config["replace_str"] = rep_str or None # pyrefly: ignore [bad-assignment]
            config["replacements"] = (
                [r.strip() for r in reps.split(",")] if reps else None # pyrefly: ignore [bad-assignment]
            )

            actions = []
            for i in range(self.action_list_widget.count()):
                txt = self.action_list_widget.item(i).text()
                atype = txt.split(" | Param: ")[0]
                param = txt.split(" | Param: ")[1] if " | Param: " in txt else None
                if param and ("Seconds" in atype):
                    with contextlib.suppress(Exception):
                        param = float(param)
                elif param and ("Number X" in atype):
                    with contextlib.suppress(Exception):
                        param = int(param)

                actions.append({"type": atype, "param": param})

            if not actions:
                actions.append({"type": "Extract High-Res Preview URL", "param": None})

            config["actions"] = actions # pyrefly: ignore [bad-assignment]
            config["login_config"] = { # pyrefly: ignore [bad-assignment]
                "url": self.gen_login_url.text().strip() or None,
                "username": self.gen_username.text().strip() or None,
                "password": self.gen_password.text().strip() or None,
            }

            try:
                config["skip_first"] = int(self.skip_first_input.text()) # pyrefly: ignore [bad-assignment]
                config["skip_last"] = int(self.skip_last_input.text()) # pyrefly: ignore [bad-assignment]
            except Exception:
                config["skip_first"] = 0 # pyrefly: ignore [bad-assignment]
                config["skip_last"] = 0 # pyrefly: ignore [bad-assignment]

        elif crawler_type_idx >= 1:
            if crawler_type_idx == 2:
                board_type = "gelbooru"
            elif crawler_type_idx == 3:
                board_type = "sankaku"
            else:
                board_type = "danbooru"

            config["type"] = "board"
            config["board_type"] = board_type
            config["url"] = self.board_url.text().strip()
            config["tags"] = self.board_tags.text().strip()

            config["resource"] = self.board_resource.text().strip() or "posts"

            extra_params_str = self.board_extra_params.text().strip()
            config["extra_params"] = {} # pyrefly: ignore [bad-assignment]
            if extra_params_str:
                try:
                    pairs = extra_params_str.split("&")
                    for p in pairs:
                        if "=" in p:
                            k, v = p.split("=", 1)
                            config["extra_params"][k.strip()] = v.strip() # pyrefly: ignore [unsupported-operation]
                except Exception:
                    print("Error parsing extra params")

            try:
                config["limit"] = int(self.board_limit.text().strip()) # pyrefly: ignore [bad-assignment]
                config["max_pages"] = int(self.board_max_pages.text().strip()) # pyrefly: ignore [bad-assignment]
            except ValueError:
                QMessageBox.warning(
                    self, "Error", "Limit and Max Pages must be integers."
                )
                return

            config["login_config"] = { # pyrefly: ignore [bad-assignment]
                "username": self.board_username.text().strip() or None,
                "password": self.board_apikey.text().strip() or None,
            }

            if not config["url"].startswith("http"):
                config["url"] = "https://" + config["url"]

            config["screenshot_dir"] = None # pyrefly: ignore [bad-assignment]
            config["skip_first"] = 0 # pyrefly: ignore [bad-assignment]
            config["skip_last"] = 0 # pyrefly: ignore [bad-assignment]

        # Start UI state
        self.run_button.hide()
        self.cancel_button.show()
        self.status_label.setText("Initializing...")
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)
        self.log_window.clear_log()
        self.log_window.show()

        # Worker
        self.downloaded_files = []
        self.worker = ImageCrawlWorker(config)
        self.worker.status.connect(self.log_window.append_log)
        self.worker.error.connect(self.log_window.append_log)
        self.worker.image_downloaded.connect(self.downloaded_files.append)
        self.worker.sig_finished.connect(self.on_crawl_done)
        self.worker.start()

    @Slot()
    def cancel_crawl(self):
        if self.worker and self.worker.isRunning():
            self.log_window.append_log("🛑 Stopping crawler...")
            self.worker.stop()
            if not self.worker.wait(3000):
                self.worker.terminate()
                self.worker.wait(1000)
            self._is_crawling = False
            self.qml_crawling_changed.emit()
            self.on_crawl_done(0, "Cancelled by user.")

    def _delete_pruned_file(self, path: str):
        """Helper to remove a pruned image and all its associated metadata files (.json, .txt)."""
        try:
            if os.path.exists(path):
                os.remove(path)
            for ext in [".json", ".txt"]:
                meta_path = os.path.splitext(path)[0] + ext
                if os.path.exists(meta_path):
                    os.remove(meta_path)
        except Exception as e:
            print(f"Error removing pruned file/metadata: {e}")

    def on_crawl_done(self, count, message):  # noqa: C901
        self.run_button.show()
        self.cancel_button.hide()
        self.progress_bar.hide()
        self.status_label.setText(message)

        is_cancelled = "Cancelled" in message or "Critical" in message
        mode = self.selection_mode_combo.currentText()

        if is_cancelled:
            if "Manual Selection" in mode or "Automated Selection" in mode:
                for path in self.downloaded_files:
                    self._delete_pruned_file(path)
            return

        if self.downloaded_files:
            if "Manual Selection" in mode:
                from gui.src.components.dialogs.crawler_selection_dialogs import ManualSelectionDialog
                dialog = ManualSelectionDialog(self.downloaded_files, self)
                result = dialog.exec()

                if result == QDialog.DialogCode.Accepted:
                    kept_count = 0
                    for path in self.downloaded_files:
                        chk = dialog.checkboxes.get(path)
                        if chk and chk.isChecked():
                            kept_count += 1
                        else:
                            self._delete_pruned_file(path)

                    new_msg = f"Crawl finished. Manually kept **{kept_count}** of **{len(self.downloaded_files)}** image(s)!"
                    self.status_label.setText(new_msg)
                    QMessageBox.information(
                        self, "Done", f"{new_msg}\nSaved to: {self.download_dir_path.text()}"
                    )
                else:
                    for path in self.downloaded_files:
                        self._delete_pruned_file(path)
                    self.status_label.setText("Crawl discarded.")
                    QMessageBox.information(self, "Cancelled", "Crawl discarded. All downloaded files removed.")

            elif "Automated Selection" in mode:
                from gui.src.components.dialogs.crawler_selection_dialogs import (
                    DeduplicationPruningDialog,
                    DuplicateConfigDialog,
                    run_duplicate_scan,
                )

                config_dialog = DuplicateConfigDialog(self)
                config_result = config_dialog.exec()

                if config_result == QDialog.DialogCode.Accepted:
                    dup_config = config_dialog.get_config()

                    # Run duplicate scan
                    dupes_map = run_duplicate_scan(self.downloaded_files, dup_config, self)

                    # Open Pruning Dialog
                    prune_dialog = DeduplicationPruningDialog(self.downloaded_files, dupes_map, self)
                    prune_result = prune_dialog.exec()

                    if prune_result == QDialog.DialogCode.Accepted:
                        kept_count = 0
                        for path in self.downloaded_files:
                            chk = prune_dialog.checkboxes.get(path)
                            if chk and chk.isChecked():
                                kept_count += 1
                            else:
                                self._delete_pruned_file(path)

                        new_msg = f"Crawl finished. Auto-pruned duplicates. Kept **{kept_count}** of **{len(self.downloaded_files)}** image(s)!"
                        self.status_label.setText(new_msg)
                        QMessageBox.information(
                            self, "Done", f"{new_msg}\nSaved to: {self.download_dir_path.text()}"
                        )
                    else:
                        for path in self.downloaded_files:
                            self._delete_pruned_file(path)
                        self.status_label.setText("Crawl discarded.")
                        QMessageBox.information(self, "Cancelled", "Crawl discarded. All downloaded files removed.")
                else:
                    for path in self.downloaded_files:
                        self._delete_pruned_file(path)
                    self.status_label.setText("Crawl discarded.")
                    QMessageBox.information(self, "Cancelled", "Crawl discarded. All downloaded files removed.")
            else:
                QMessageBox.information(
                    self, "Done", f"{message}\nSaved to: {self.download_dir_path.text()}"
                )


__all__ = ["_CrawlWorkerMixin"]
