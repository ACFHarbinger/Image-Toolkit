"""Extraction queue management (add/remove/reorder-by-load, sequential vs
parallel processing) and the "5. Results Gallery Section" build (output
gallery, queue box, search input, pagination).

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import copy
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, cast

from PySide6.QtCore import QPoint, Qt, QThreadPool, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ....components import ClickableLabel, MarqueeScrollArea
from ....helpers.core.queue_execution_worker import QueueExecutionWorker

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class _QueueManagementMixin:
    """Extraction queue management and the Results Gallery / Queue section."""

    active_queue_worker: Optional[QueueExecutionWorker]

    def _build_results_section(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Builds "5. Results Gallery Section" and adds it to self.main_layout."""
        self.gallery_scroll_area: Optional[QScrollArea] = MarqueeScrollArea()
        self.gallery_scroll_area.setWidgetResizable(True) # pyrefly: ignore [missing-attribute]
        self.gallery_scroll_area.setStyleSheet( # pyrefly: ignore [missing-attribute]
            """
            QScrollArea {
                border: 1px solid #4f545c;
                background-color: #2c2f33;
                border-radius: 8px;
            }
            QScrollBar:vertical {
                border: none;
                background: #2c2f33;
                width: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #00BCD4;
                min-height: 20px;
                border-radius: 6px;
                margin: 0 2px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                subcontrol-position: none;
            }
            QScrollBar:horizontal {
                border: none;
                background: #2c2f33;
                height: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: #00BCD4;
                min-width: 20px;
                border-radius: 6px;
                margin: 2px 0;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                subcontrol-position: none;
            }
        """
        )
        self.gallery_scroll_area.setMinimumHeight(600) # pyrefly: ignore [missing-attribute]

        self.gallery_container = QWidget()
        self.gallery_container.setStyleSheet("QWidget { background-color: #2c2f33; }")

        self.gallery_layout: Optional[QGridLayout] = QGridLayout(self.gallery_container)
        self.gallery_layout.setAlignment( # pyrefly: ignore [missing-attribute]
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.gallery_layout.setSpacing(3) # pyrefly: ignore [missing-attribute]
        self.gallery_scroll_area.setWidget(self.gallery_container) # pyrefly: ignore [missing-attribute]

        self.gallery_scroll_area.selection_changed.connect( # pyrefly: ignore [missing-attribute]
            self.handle_marquee_selection
        )

        # Setup Queue UI Group Box
        self.queue_group = QGroupBox("Extraction Queue")
        queue_layout = QVBoxLayout(self.queue_group)
        queue_layout.setContentsMargins(10, 10, 10, 10)

        self.queue_list = QListWidget()
        self.queue_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(self.show_queue_context_menu)
        self.queue_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.queue_list.model().rowsMoved.connect(lambda *_: self._on_queue_reordered())
        queue_layout.addWidget(self.queue_list)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Execution Mode:"))
        self.combo_queue_mode = QComboBox()
        self.combo_queue_mode.addItems(["Sequentially", "Parallel (Multiprocessing)"])
        controls_layout.addWidget(self.combo_queue_mode)

        self.btn_process_queue = QPushButton("⚙️ Process Queue")
        self.btn_process_queue.clicked.connect(self.process_queue)
        self.btn_process_queue.setStyleSheet(
            "QPushButton { font-weight: bold; background-color: #2ecc71; color: white; padding: 4px 8px; }"
        )
        controls_layout.addWidget(self.btn_process_queue)

        self.btn_clear_queue = QPushButton("🗑️ Clear Queue")
        self.btn_clear_queue.clicked.connect(self.clear_queue)
        controls_layout.addWidget(self.btn_clear_queue)

        queue_layout.addLayout(controls_layout)

        # Match the Extraction Queue section's height to the Extraction
        # Settings section (self.extract_group, built earlier in __init__):
        # cap the queue list so the whole queue group renders at the same
        # height as the settings group. The settings group's sizeHint is the
        # source of truth; the queue group's non-list overhead (title bar,
        # margins, spacing, and the controls row, i.e. group sizeHint minus
        # the list's own sizeHint) is subtracted so the LIST height is what's
        # tuned. Larger queues scroll inside the widget, and the gallery
        # below keeps its space.
        settings_h = self.extract_group.sizeHint().height()
        queue_overhead = (
            self.queue_group.sizeHint().height() - self.queue_list.sizeHint().height()
        )
        target_list_h = max(0, settings_h - queue_overhead)
        self.queue_list.setMinimumHeight(target_list_h)
        self.queue_list.setMaximumHeight(target_list_h)

        self.main_layout.addWidget(self.queue_group)
        self.queue_group.setVisible(self.extraction_queue_enabled)

        # Deferred gallery paths while a queue run is active: per-item
        # completion appends here and the finished/error handler performs ONE
        # gallery rebuild (see _on_queue_item_completed for why per-item
        # rebuilds freeze the UI).
        self._queue_pending_gallery_paths = []

        # Add shared search input (Lazy Search)
        self.main_layout.addWidget(self.search_input)

        self.main_layout.addWidget(self.gallery_scroll_area, 1) # pyrefly: ignore [bad-argument-type]
        self.main_layout.addWidget(
            self.pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
        )

        self.extraction_status_label = QLabel("Ready.")
        self.extraction_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.extraction_status_label.setStyleSheet(
            "color: #666; font-style: italic; padding: 8px;"
        )
        self.extraction_status_label.hide()
        self.main_layout.addWidget(self.extraction_status_label)

    @Slot()
    def clear_queue(self: "VideoExtractorSubTabHostProtocol"):
        self.extraction_queue.clear()
        self._update_queue_ui()
        self.extraction_status_label.setText("Queue cleared.")
        self.extraction_status_label.show()

    @Slot(QPoint)
    def show_queue_context_menu(self: "VideoExtractorSubTabHostProtocol", pos: QPoint):
        item = self.queue_list.itemAt(pos)
        if not item:
            return
        idx = self.queue_list.row(item)
        if idx < 0 or idx >= len(self.extraction_queue):
            return

        menu = QMenu(cast(QWidget, self))
        menu.setStyleSheet(
            "QMenu { background-color: #1e1f22; color: white; border: 1px solid #4f545c; }"
        )
        load_action = menu.addAction("✏️ Load Configurations")
        remove_action = menu.addAction("❌ Remove")

        action = menu.exec(self.queue_list.mapToGlobal(pos))
        if action == load_action:
            self.load_extraction_config(idx)
        elif action == remove_action:
            self.remove_queue_item(idx)

    def remove_queue_item(self: "VideoExtractorSubTabHostProtocol", idx: int):
        if 0 <= idx < len(self.extraction_queue):
            self.extraction_queue.pop(idx)
            self._update_queue_ui()
            self.extraction_status_label.setText("Removed item from queue.")
            self.extraction_status_label.show()

    def load_extraction_config(self: "VideoExtractorSubTabHostProtocol", idx: int):  # noqa: C901
        if idx < 0 or idx >= len(self.extraction_queue):
            return
        item = self.extraction_queue[idx]
        v_path = item.get("video_path")
        if not v_path or not os.path.exists(v_path):
            QMessageBox.warning(
                cast(QWidget, self), "File Not Found", f"The video file '{v_path}' no longer exists."
            )
            return

        # Load video if not already open
        if self.video_path != v_path:
            self.load_media(v_path)

        # Set start and end time from config
        self.start_time_ms = item.get("start_ms", 0)
        self.end_time_ms = item.get("end_ms", 0)
        self.btn_set_start.setText(
            f"Start [{self._format_time(self.start_time_ms)}]"
            if self.start_time_ms
            else "Set Start [00:00]"
        )
        self.btn_set_end.setText(
            f"End [{self._format_time(self.end_time_ms)}]"
            if self.end_time_ms
            else "Set End [00:00]"
        )

        # Load cuts
        self.cuts_ms = copy.deepcopy(item.get("cuts_ms", []))
        self._update_cuts_label()

        # Load interval/smart extract
        self.spin_interval.setValue(item.get("frame_interval", 1))
        self.check_smart_extract.setChecked(item.get("smart_extract", False))
        smart_method = item.get("smart_method")
        if smart_method:
            self.combo_smart_method.setCurrentText(smart_method)

        # Target resolution
        target_res = item.get("target_resolution")
        if target_res:
            res_str = f"{target_res[0]}x{target_res[1]}"
            for i in range(self.combo_extract_size.count()):
                if self.combo_extract_size.itemText(i) == res_str:
                    self.combo_extract_size.setCurrentIndex(i)
                    break
        else:
            self.combo_extract_size.setCurrentText("Native")

        # Load engine
        use_ffmpeg = item.get("use_ffmpeg", True)
        self.combo_engine.setCurrentText("FFmpeg" if use_ffmpeg else "MoviePy")

        # Load speed
        speed = item.get("speed", 1.0)
        if isinstance(speed, float):
            if speed == 1.0:
                speed_str = "1x"
            elif speed == 0.5:
                speed_str = "0.5x"
            elif speed == 0.25:
                speed_str = "0.25x"
            elif speed == 1.5:
                speed_str = "1.5x"
            elif speed == 2.0:
                speed_str = "2x"
            elif speed == 4.0:
                speed_str = "4x"
            else:
                speed_str = f"{speed:g}x"
        else:
            speed_str = str(speed)
            if not speed_str.endswith("x"):
                speed_str += "x"
        self.combo_speed.setCurrentText(speed_str)

        # Load mute audio
        self.check_mute_audio.setChecked(item.get("mute_audio", False))

        # Load fps (for gif or others)
        self.spin_gif_fps.setValue(item.get("fps", 24))

        # Jump to start_ms in media player
        if self.start_time_ms > 0 and self.media_player:
            self.media_player.setPosition(self.start_time_ms)
            self.slider.setValue(self.start_time_ms)
            cast(QLabel, self.lbl_current_time).setText(self._format_time(self.start_time_ms)) # pyrefly: ignore [missing-attribute]

        # Update active video config dictionary so switching tabs doesn't lose it
        config = self.active_videos_config.get(v_path, {})
        config["start_time_ms"] = self.start_time_ms
        config["end_time_ms"] = self.end_time_ms
        config["cuts_ms"] = copy.deepcopy(self.cuts_ms)
        config["spin_interval"] = item.get("frame_interval", 1)
        config["check_smart_extract"] = item.get("smart_extract", False)
        config["combo_smart_method"] = item.get("smart_method", "")
        config["check_mute_audio"] = item.get("mute_audio", False)
        config["spin_gif_fps"] = item.get("fps", 24)
        config["combo_extract_size"] = self.combo_extract_size.currentText()
        config["media_position"] = self.start_time_ms
        self.active_videos_config[v_path] = config

        self.extraction_status_label.setText(
            f"Loaded configurations from queue item #{idx + 1}."
        )
        self.extraction_status_label.show()

    def _update_queue_ui(self: "VideoExtractorSubTabHostProtocol"):
        self.queue_list.clear()
        for idx, item in enumerate(self.extraction_queue):
            v_name = Path(item["video_path"]).name
            t_type = item["type"].upper()
            start_fmt = time.strftime("%M:%S", time.gmtime(item["start_ms"] / 1000.0))
            end_fmt = (
                time.strftime("%M:%S", time.gmtime(item["end_ms"] / 1000.0))
                if item["end_ms"] != -1
                else "End"
            )
            list_item = QListWidgetItem(
                f"{idx + 1}. [{t_type}] {v_name} ({start_fmt} - {end_fmt})"
            )
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.queue_list.addItem(list_item)

        enabled = len(self.extraction_queue) > 0
        self.btn_process_queue.setEnabled(enabled)
        self.btn_clear_queue.setEnabled(enabled)

    def _on_queue_reordered(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Drag-and-drop (InternalMove) callback: resync extraction_queue's
        processing order from the list widget's new visual order, then
        re-run _update_queue_ui to refresh the "n." position captions."""
        self.extraction_queue = [
            self.queue_list.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.queue_list.count())
        ]
        self._update_queue_ui()

    def _on_queue_toggle_changed(self: "VideoExtractorSubTabHostProtocol"):
        if hasattr(self, "queue_group"):
            self.queue_group.setVisible(self.extraction_queue_enabled)

    @Slot()
    def process_queue(self: "VideoExtractorSubTabHostProtocol"):
        if not self.extraction_queue:
            return

        mode = self.combo_queue_mode.currentText()
        is_parallel = "Parallel" in mode

        self.btn_process_queue.setEnabled(False)
        self.btn_clear_queue.setEnabled(False)
        self.combo_queue_mode.setEnabled(False)

        self.extraction_progress_bar.setValue(0)
        self.extraction_progress_bar.show()
        self.extraction_status_label.setText(f"Processing queue ({mode})...")
        self.extraction_status_label.show()

        # Deferred gallery paths for this run (see _on_queue_item_completed).
        self._queue_pending_gallery_paths = []

        # Pass a COPY: the worker iterates its own list while the tab
        # removes completed items from self.extraction_queue per item; sharing
        # the same list object would let the tab's pop() skip the worker's
        # pending iterations.
        worker = QueueExecutionWorker(list(self.extraction_queue), parallel=is_parallel)
        self.active_queue_worker = worker
        worker.signals.progress.connect(self._on_queue_progress)
        worker.signals.item_completed.connect(self._on_queue_item_completed)
        worker.signals.finished.connect(self._on_queue_processing_finished)
        worker.signals.error.connect(self._on_queue_processing_error)

        QThreadPool.globalInstance().start(worker)

    @Slot(int, int)
    def _on_queue_progress(self: "VideoExtractorSubTabHostProtocol", completed: int, total: int):
        self.extraction_progress_bar.setMaximum(max(total, 1))
        self.extraction_progress_bar.setValue(completed)

    def _queue_result_paths(self: "VideoExtractorSubTabHostProtocol", res: dict) -> List[str]:
        """Collect the files a queue item produced (saved_files or output_path)."""
        paths = []
        if res.get("status") != "success":
            return paths
        if res.get("saved_files"):
            paths.extend(res["saved_files"])
        elif res.get("output_path"):
            paths.append(res["output_path"])
        return paths

    def _queue_result_metadata(self: "VideoExtractorSubTabHostProtocol", item: dict) -> dict:
        """Build the extraction-history metadata for a queued item, mirroring
        _get_current_extraction_metadata() but sourced from the queue config
        (the worker is stateless, so the UI state can't be trusted at the
        moment the queue finishes)."""
        engine = "FFmpeg" if item.get("use_ffmpeg", True) else "MoviePy"
        return {
            "video_path": item.get("video_path", ""),
            "start_ms": item.get("start_ms", 0),
            "end_ms": item.get("end_ms", 0),
            "cuts_ms": copy.deepcopy(item.get("cuts_ms", [])),
            "tags_ms": [],
            "output_size": "",
            "extract_vertical": False,
            "gif_fps": int(item.get("fps", 24)),
            "mute_audio": bool(item.get("mute_audio", False)),
            "engine": engine,
            "frame_interval": int(item.get("frame_interval", 1)),
            "smart_extract": bool(item.get("smart_extract", False)),
            "smart_method": item.get("smart_method", ""),
            "speed": str(item.get("speed", 1.0)),
            "timestamp": time.time(),
        }

    @Slot(int, dict, dict)
    def _on_queue_item_completed(self: "VideoExtractorSubTabHostProtocol", index: int, res: dict, item: dict):
        """Per-item completion: record the extraction into recent extractions
        (previously queue results never appeared there) and remove the
        finished item from the queue list promptly.

        The gallery update is DEFERRED to _on_queue_processing_finished (or
        _on_queue_processing_error): rebuilding the gallery per item runs
        refresh_gallery_view() -> cancel_loading() -> thread_pool.
        waitForDone(-1) on the UI thread, and the gallery shares
        QThreadPool.globalInstance() with the queue worker itself, so that
        wait blocks until the WHOLE queue finishes -- the observed freeze
        while queued extractions run. Paths are accumulated and one rebuild
        happens once the worker is done.

        item is the original queue config handed to the worker, so the
        finished entry is removed by identity; index alignment is not reliable
        once earlier items have already been popped (parallel mode completes
        out of order).

        Previously only _on_queue_processing_finished ran (once the WHOLE
        queue was done), so items lingered in the list after completing and
        their outputs were never recorded in extraction history.
        """
        paths = self._queue_result_paths(res)
        if not paths:
            return

        # Record first (so a failure below doesn't drop the history entry)
        metadata = self._queue_result_metadata(item)
        metadata["mode"] = item.get("type", "range")
        self._record_extraction(paths, metadata)

        # Remove the finished item from the queue list immediately.
        # Match by identity first (sequential mode: same process), then by
        # value (parallel mode: the config was pickled through multiprocessing
        # so the worker returns a copy), then fall back to index.
        removed = False
        for i, queued in enumerate(self.extraction_queue):
            if queued is item or queued == item or (not item and i == index):
                self.extraction_queue.pop(i)
                removed = True
                break
        if removed:
            self._update_queue_ui()

        # Defer the gallery update: see class docstring above. Existence
        # filtering still happens here so a phantom path never enters the
        # pending list.
        existing = [p for p in paths if os.path.exists(p)]
        if existing:
            self._queue_pending_gallery_paths.extend(existing)

    def _add_queue_results_to_gallery(self: "VideoExtractorSubTabHostProtocol", paths: List[str]):
        # Only show files that actually exist on disk -- the gallery does not
        # verify existence itself, so a worker-reported path that is relative
        # or otherwise doesn't match where the file landed would otherwise show
        # a phantom card ("appears in gallery but not in the output dir").
        existing = [p for p in paths if os.path.exists(p)]
        if not existing:
            return
        self._refresh_extracted_stems_cache()
        self.start_loading_gallery(existing, append=True)
        self.current_extracted_paths = self.gallery_image_paths[:]

        for path, widget in self.source_path_to_widget.items():
            label = widget.findChild(ClickableLabel)
            if label:
                self._update_source_label_style(
                    path, label, path == getattr(self, "video_path", None)
                )

    def _on_queue_processing_finished(self: "VideoExtractorSubTabHostProtocol", results):
        self.active_queue_worker = None
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()

        self.btn_process_queue.setEnabled(True)
        self.btn_clear_queue.setEnabled(True)
        self.combo_queue_mode.setEnabled(True)

        # ONE gallery rebuild for the whole run: per-item completion defers
        # its gallery update (see _on_queue_item_completed) because a per-item
        # rebuild blocks the UI thread on thread_pool.waitForDone(-1) while
        # the queue worker is still running. Flush everything here.
        deferred = list(self._queue_pending_gallery_paths)
        self._queue_pending_gallery_paths = []

        # Only collect gallery paths here. Recording into recent
        # extractions is done per-item in _on_queue_item_completed (which has
        # the real queue config). The old fallback re-recorded results with
        # _queue_result_metadata({}) -- an empty dict -- which wrote
        # "Unknown Video (00:00:000 - 00:00:000)" entries for every queued
        # item after restart. Do NOT record with empty metadata.
        new_paths: List[str] = []
        errors = []
        for res in results:
            paths = self._queue_result_paths(res)
            if paths:
                for path in paths:
                    if str(path) not in self.master_image_paths:
                        new_paths.append(path)
            else:
                errors.append(res.get("message", "Unknown error"))

        self.extraction_queue.clear()
        self._update_queue_ui()

        all_paths = deferred + [p for p in new_paths if p not in deferred]
        if all_paths:
            self._add_queue_results_to_gallery(all_paths)

        if errors:
            QMessageBox.warning(
                cast(QWidget, self),
                "Queue Extraction Completed with Errors",
                "Processed queue items. Errors encountered:\n" + "\n".join(errors),
            )
        else:
            QMessageBox.information(
                cast(QWidget, self),
                "Success",
                f"Queue execution complete! Processed all items. Extracted {len(all_paths)} items.",
            )

        self._maybe_finish_close()

    def _on_queue_processing_error(self: "VideoExtractorSubTabHostProtocol", error_msg):
        self.active_queue_worker = None
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()

        self.btn_process_queue.setEnabled(True)
        self.btn_clear_queue.setEnabled(True)
        self.combo_queue_mode.setEnabled(True)

        # Flush any per-item results that completed before the failure so
        # they still appear in the gallery.
        if self._queue_pending_gallery_paths:
            self._add_queue_results_to_gallery(self._queue_pending_gallery_paths)
            self._queue_pending_gallery_paths = []

        if "cancelled" not in error_msg.lower():
            QMessageBox.warning(cast(QWidget, self), "Queue Processing Error", error_msg)

        self._maybe_finish_close()

    # ------------------------------------------------------------------
    # App-close deferral (headless keep-alive while extractions run)
    # ------------------------------------------------------------------

    def has_active_extractions(self: "VideoExtractorSubTabHostProtocol") -> bool:
        """True while a queue worker OR a single (GIF/video) extraction is
        still running. MainWindow.closeEvent uses this to keep the process
        alive headlessly until the work finishes (Bug 1)."""
        return (
            getattr(self, "active_queue_worker", None) is not None
            or getattr(self, "active_extraction_worker", None) is not None
        )

    def set_close_when_finished(self: "VideoExtractorSubTabHostProtocol", callback) -> None:
        """Register a callback invoked once all extractions finish (used by
        MainWindow to complete a deferred close)."""
        self._close_when_finished = callback

    def _maybe_finish_close(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Fire the deferred-close callback once no extraction is active."""
        if self.has_active_extractions():
            return
        callback = getattr(self, "_close_when_finished", None)
        if callback is None:
            return
        self._close_when_finished = None
        callback()


__all__ = ["_QueueManagementMixin"]
