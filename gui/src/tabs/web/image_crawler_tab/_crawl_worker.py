"""ImageCrawlWorker dispatch, cancellation, and post-crawl pruning dialogs.

Extracted from ``image_crawler_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import contextlib
import json
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
            # Unbounded wait — QThread.terminate() is a heap-corruption
            # class (see #461). Crawler.stop() + requestInterruption()
            # is the cooperative cancel path.
            self.worker.wait()
            self._is_crawling = False
            self.qml_crawling_changed.emit()
            self.on_crawl_done(0, "Cancelled by user.")

    def _delete_pruned_file(self, clean_path: str):
        """Remove a downloaded image file and any associated sidecar files (.json, .txt)."""
        try:
            if not clean_path or not isinstance(clean_path, str):
                return

            # Normalize: strip query params, URL fragments, whitespace
            target = os.path.normpath(clean_path.split("?")[0].split("#")[0].strip())
            if not target:
                return

            d_dir = ""
            if hasattr(self, "download_dir_path") and hasattr(self.download_dir_path, "text"):
                d_dir = self.download_dir_path.text().strip()

            # Build candidate list: exact path + download_dir/filename fallback
            fname = os.path.basename(target)
            candidates = [target]
            if d_dir and fname:
                candidates.append(os.path.join(d_dir, fname))

            for candidate in candidates:
                if candidate and os.path.isfile(candidate):
                    try:
                        os.remove(candidate)
                        print(f"[CrawlWorker] Deleted: {candidate}")
                    except Exception as ex:
                        print(f"[CrawlWorker] Error removing {candidate}: {ex}")

                    # Remove sidecar metadata files
                    stem = os.path.splitext(candidate)[0]
                    for ext in (".json", ".txt"):
                        sidecar = stem + ext
                        if os.path.isfile(sidecar):
                            with contextlib.suppress(Exception):
                                os.remove(sidecar)
                    break
        except Exception as e:
            print(f"[CrawlWorker] Error removing pruned file: {e}")

    def on_crawl_done(self, count, message):  # noqa: C901
        self.run_button.show()
        self.cancel_button.hide()
        self.progress_bar.hide()
        self.status_label.setText(message)

        is_cancelled = "Cancelled" in message or "Critical" in message
        mode = self.selection_mode_combo.currentText()

        if is_cancelled:
            if "Manual Selection" in mode or "Automated Selection" in mode:
                for item in self.downloaded_files:
                    self._delete_pruned_file(item)
            return

        if self.downloaded_files:
            if "Manual Selection" in mode:
                from gui.src.components.dialogs.crawler_selection_dialogs import ManualSelectionDialog
                sf, sl = 0, 0
                if hasattr(self, "skip_first_input") and hasattr(self.skip_first_input, "text"):
                    with contextlib.suppress(Exception):
                        sf = int(self.skip_first_input.text().strip())
                if hasattr(self, "skip_last_input") and hasattr(self.skip_last_input, "text"):
                    with contextlib.suppress(Exception):
                        sl = int(self.skip_last_input.text().strip())

                dialog = ManualSelectionDialog(self.downloaded_files, self, skip_first=sf, skip_last=sl)
                result = dialog.exec()

                if result == QDialog.DialogCode.Accepted:
                    kept_paths = set(dialog.get_kept_paths())
                    pruned_paths = set(dialog.get_pruned_paths())

                    pruned_count = 0
                    for path in pruned_paths:
                        self._delete_pruned_file(path)
                        pruned_count += 1

                    kept_count = len(kept_paths)
                    new_msg = f"Crawl finished. Manually kept **{kept_count}** of **{len(self.downloaded_files)}** image(s) ({pruned_count} deleted)!"
                    self.status_label.setText(new_msg)
                    QMessageBox.information(
                        self, "Done", f"{new_msg}\nSaved to: {self.download_dir_path.text()}"
                    )
                else:
                    # Cancel (Discard All): delete every downloaded file
                    for raw_item in self.downloaded_files:
                        clean_path = ""
                        if isinstance(raw_item, dict):
                            clean_path = raw_item.get("path", "")
                        elif isinstance(raw_item, str) and raw_item.strip().startswith("{"):
                            with contextlib.suppress(Exception):
                                clean_path = json.loads(raw_item).get("path", "")
                        else:
                            clean_path = str(raw_item)
                        if clean_path:
                            self._delete_pruned_file(clean_path)
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
