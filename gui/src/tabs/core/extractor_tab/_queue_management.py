"""Extraction queue management (add/remove/reorder-by-load, sequential vs
parallel processing) and the "5. Results Gallery Section" build (output
gallery, queue box, search input, pagination).

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import contextlib
import copy
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, cast

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ....components import ClickableLabel, VirtualGallery
from ....helpers import ImageLoaderWorker, VideoLoaderWorker
from ....helpers.core.queue_execution_worker import QueueExecutionWorker
from ....styles import set_button_role

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol

# In-process queue per-item states.
_ST_PENDING = "pending"
_ST_PROCESSING = "processing"
_ST_DONE = "done"
_ST_ERROR = "error"
_ST_ICON = {
    _ST_PENDING: "⏳",
    _ST_PROCESSING: "▶️",
    _ST_DONE: "✓",
    _ST_ERROR: "✗",
}


def _inprocess_row_label(idx: int, item: dict, status: str) -> str:
    """Pure row-label builder for the In Process list (Qt-free, unit-tested)."""
    icon = _ST_ICON.get(status, _ST_ICON[_ST_PENDING])
    try:
        v_name = Path(item.get("video_path") or "?").name
    except Exception:
        v_name = "?"
    t_type = str(item.get("type", "range")).upper()
    start_fmt = time.strftime("%M:%S", time.gmtime(int(item.get("start_ms", 0)) / 1000.0))
    end_ms = item.get("end_ms", -1)
    end_fmt = (
        time.strftime("%M:%S", time.gmtime(int(end_ms) / 1000.0))
        if end_ms not in (-1, None)
        else "End"
    )
    return f"{icon} {idx + 1}. [{t_type}] {v_name} ({start_fmt} - {end_fmt})"


class _QueueManagementMixin:
    """Extraction queue management and the Results Gallery / Queue section."""

    active_queue_worker: Optional[QueueExecutionWorker] = None
    _close_progress_dialog: Optional[Any] = None
    _close_when_finished: Optional[Any] = None
    _queue_total_count: int = 0
    _queue_completed_count: int = 0
    _current_queue_item_title: str = ""
    inprocess_items: List[dict] = []
    _inprocess_status: List[str] = []
    _inprocess_awaiting_confirm: bool = False

    def set_close_progress_dialog(self: "VideoExtractorSubTabHostProtocol", dialog: Any) -> None:
        """Attach the TaskCloseProgressDialog to receive live progress updates."""
        self._close_progress_dialog = dialog

    def _build_results_section(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Builds "5. Results Gallery Section" and adds it to self.main_layout."""
        # Virtual-scroll gallery (GUI/UX §2.1 Option A) — replaces the old
        # MarqueeScrollArea + QGridLayout + ClickableLabel grid; pagination is
        # dropped and selection lives in the view's QItemSelectionModel.
        def _gallery_worker(path: str, target_size: int):
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                return VideoLoaderWorker(path, target_size)
            return ImageLoaderWorker(path, target_size)

        self.gallery = VirtualGallery(self, worker_factory=_gallery_worker)
        self.gallery.setMinimumHeight(600)
        self.gallery.path_clicked.connect(self.handle_thumbnail_single_click)
        self.gallery.path_activated.connect(self.handle_thumbnail_double_click)
        self.gallery.path_right_clicked.connect(self.show_image_context_menu)
        self.gallery.selection_changed.connect(self._sync_selection_from_gallery)

        # Setup Queue UI Group Box
        self.queue_group = QGroupBox("Extraction Queue")
        queue_layout = QVBoxLayout(self.queue_group)
        queue_layout.setContentsMargins(10, 10, 10, 10)

        # Two side-by-side lists: the left "On Hold" queue the user edits, and
        # the right "In Process" queue that shows the batch currently being
        # processed (pending / running / done / failed per item). Clicking
        # Process Queue moves the left list into the right one; the right list
        # is only cleared once the user acknowledges the completion dialog.
        lists_row = QHBoxLayout()
        lists_row.setSpacing(10)

        onhold_col = QVBoxLayout()
        onhold_col.setSpacing(2)
        onhold_col.addWidget(QLabel("On Hold — editable"))
        self.queue_list = QListWidget()
        self.queue_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(self.show_queue_context_menu)
        self.queue_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.queue_list.model().rowsMoved.connect(lambda *_: self._on_queue_reordered())
        onhold_col.addWidget(self.queue_list)
        lists_row.addLayout(onhold_col, 1)

        inprocess_col = QVBoxLayout()
        inprocess_col.setSpacing(2)
        inprocess_col.addWidget(QLabel("In Process"))
        self.inprocess_list = QListWidget()
        self.inprocess_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.inprocess_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        inprocess_col.addWidget(self.inprocess_list)
        lists_row.addLayout(inprocess_col, 1)

        queue_layout.addLayout(lists_row)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Execution Mode:"))
        self.combo_queue_mode = QComboBox()
        self.combo_queue_mode.addItems(["Sequentially", "Parallel (Multiprocessing)"])
        controls_layout.addWidget(self.combo_queue_mode)

        self.btn_process_queue = QPushButton("⚙️ Process Queue")
        self.btn_process_queue.clicked.connect(self.process_queue)
        set_button_role(self.btn_process_queue, "success")
        controls_layout.addWidget(self.btn_process_queue)

        self.btn_clear_queue = QPushButton("🗑️ Clear Queue")
        self.btn_clear_queue.clicked.connect(self.clear_queue)
        controls_layout.addWidget(self.btn_clear_queue)

        queue_layout.addLayout(controls_layout)

        # Match the Extraction Queue section's height to the Extraction
        # Settings section (self.extract_group). The two lists sit side by
        # side and are identical, so the row's height contribution is one
        # list's sizeHint; subtracting that from the group sizeHint isolates
        # the fixed overhead (title bar, margins, column headers, controls
        # row), and capping BOTH lists to `settings_h - overhead` keeps the
        # whole group at the settings-group height. Larger queues scroll.
        settings_h = self.extract_group.sizeHint().height()
        queue_overhead = (
            self.queue_group.sizeHint().height() - self.queue_list.sizeHint().height()
        )
        target_list_h = max(0, settings_h - queue_overhead)
        for _lst in (self.queue_list, self.inprocess_list):
            _lst.setMinimumHeight(target_list_h)
            _lst.setMaximumHeight(target_list_h)

        self.main_layout.addWidget(self.queue_group)
        self.queue_group.setVisible(self.extraction_queue_enabled)

        # Deferred gallery paths while a queue run is active: per-item
        # completion appends here and the finished/error handler performs ONE
        # gallery rebuild (see _on_queue_item_completed for why per-item
        # rebuilds freeze the UI).
        self._queue_pending_gallery_paths = []

        # Add shared search input (Lazy Search)
        self.main_layout.addWidget(self.search_input)

        self.main_layout.addWidget(self.gallery, 1)

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
            "QMenu {  color: white; border: 1px solid #4f545c; }"
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
        if not hasattr(self, "queue_list"):
            return
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

        has_items = len(self.extraction_queue) > 0
        # The Process button doubles as Cancel while a run is active and must
        # stay disabled while a finished batch is awaiting confirmation — only
        # touch its enabled state when the queue is idle.
        if not self._queue_is_busy():
            self.btn_process_queue.setEnabled(has_items)
        self.btn_clear_queue.setEnabled(has_items)

    def _queue_is_busy(self: "VideoExtractorSubTabHostProtocol") -> bool:
        """True while a worker is running or a finished batch still needs the
        user's acknowledgement — Process Queue must not start in either case."""
        return (
            getattr(self, "active_queue_worker", None) is not None
            or getattr(self, "_inprocess_awaiting_confirm", False)
        )

    def _update_inprocess_ui(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Rebuild the right-hand In Process list from inprocess_items +
        _inprocess_status, and reflect progress in the group title."""
        if not hasattr(self, "inprocess_list"):
            return
        self.inprocess_list.clear()
        for idx, item in enumerate(self.inprocess_items):
            status = (
                self._inprocess_status[idx]
                if idx < len(self._inprocess_status)
                else _ST_PENDING
            )
            self.inprocess_list.addItem(
                QListWidgetItem(_inprocess_row_label(idx, item, status))
            )
        total = len(self.inprocess_items)
        if total:
            done = sum(
                1 for s in self._inprocess_status if s in (_ST_DONE, _ST_ERROR)
            )
            self.queue_group.setTitle(f"Extraction Queue — In Process {done}/{total}")
        else:
            self.queue_group.setTitle("Extraction Queue")

    def _finalize_inprocess_from_results(
        self: "VideoExtractorSubTabHostProtocol", results: list
    ) -> None:
        """Backstop: resolve any item still pending/processing from the final
        results list (parallel mode delivers per-item status in one burst)."""
        for i, res in enumerate(results or []):
            if i < len(self._inprocess_status) and self._inprocess_status[i] in (
                _ST_PENDING,
                _ST_PROCESSING,
            ):
                self._inprocess_status[i] = (
                    _ST_DONE if res.get("status") == "success" else _ST_ERROR
                )
        self._update_inprocess_ui()

    def _clear_inprocess(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Empty the In Process queue and return the controls to idle. Called
        only after the user acknowledges completion (or on a headless close)."""
        self.inprocess_items = []
        self._inprocess_status = []
        self._inprocess_awaiting_confirm = False
        self._update_inprocess_ui()
        self._set_queue_processing_state(False)
        self._update_queue_ui()

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
        if hasattr(self, "_refresh_recent_to_queue_controls"):
            self._refresh_recent_to_queue_controls()

    def _set_queue_processing_state(self: "VideoExtractorSubTabHostProtocol", processing: bool):
        """Update button label, style, and controls for the three queue states:
        processing (run active), awaiting-confirm (run done, dialog not yet
        acknowledged), and idle. The left "On Hold" queue stays editable and
        clearable in every state — it no longer feeds the running batch."""
        self.btn_clear_queue.setEnabled(len(self.extraction_queue) > 0)
        if processing:
            self.btn_process_queue.setText("🛑 Cancel Queue")
            set_button_role(self.btn_process_queue, "danger")
            self.btn_process_queue.setEnabled(True)
            self.combo_queue_mode.setEnabled(False)
        elif getattr(self, "_inprocess_awaiting_confirm", False):
            self.btn_process_queue.setText("⚙️ Process Queue")
            set_button_role(self.btn_process_queue, "success")
            self.btn_process_queue.setEnabled(False)
            self.combo_queue_mode.setEnabled(False)
        else:
            self.btn_process_queue.setText("⚙️ Process Queue")
            set_button_role(self.btn_process_queue, "success")
            self.btn_process_queue.setEnabled(len(self.extraction_queue) > 0)
            self.combo_queue_mode.setEnabled(True)

    def cancel_queue(self: "VideoExtractorSubTabHostProtocol"):
        """Cancel the active queue processing run."""
        w = self.active_queue_worker
        if w is not None:
            with contextlib.suppress(Exception):
                w.cancel()
        # Drop the reference immediately. The worker may still be winding its
        # multiprocessing Pool down in the background and its async
        # error/finished signal can be seconds away (or never, on a wedged
        # ffmpeg child) -- a fresh "Process Queue" click must not be blocked
        # by it. Handlers below no-op for any worker that is not the current
        # one, so the stale signal is harmless.
        self.active_queue_worker = None

        # Move anything that had not finished back to the front of the On Hold
        # queue so a cancel doesn't lose queued work, then drop the batch.
        not_done = [
            item
            for item, status in zip(self.inprocess_items, self._inprocess_status, strict=False)
            if status in (_ST_PENDING, _ST_PROCESSING)
        ]
        if not_done:
            self.extraction_queue[:0] = not_done
        self.inprocess_items = []
        self._inprocess_status = []
        self._inprocess_awaiting_confirm = False
        self._update_inprocess_ui()

        self._update_queue_ui()
        self._set_queue_processing_state(False)
        self.extraction_progress_bar.hide()
        n = len(not_done)
        self.extraction_status_label.setText(
            f"Queue cancelled — {n} unfinished item{'s' if n != 1 else ''} returned to On Hold."
            if n
            else "Queue cancelled."
        )
        self.extraction_status_label.show()

    @Slot()
    def process_queue(self: "VideoExtractorSubTabHostProtocol"):
        if self.active_queue_worker is not None:
            self.cancel_queue()
            return

        if getattr(self, "_inprocess_awaiting_confirm", False):
            # A finished batch is still showing in the In Process list — the
            # user has to acknowledge it before a new run can start.
            self._prompt_inprocess_confirm()
            return

        if not self.extraction_queue:
            return

        mode = self.combo_queue_mode.currentText()
        is_parallel = "Parallel" in mode

        # Move the whole On Hold queue into the In Process queue. The left
        # list is emptied and stays independently editable while this batch
        # runs; the right list is only cleared once the user confirms the
        # completion dialog (or on a headless app close).
        self.inprocess_items = list(self.extraction_queue)
        self._inprocess_status = [_ST_PENDING] * len(self.inprocess_items)
        self.extraction_queue.clear()
        self._update_queue_ui()
        self._update_inprocess_ui()

        self._set_queue_processing_state(True)

        self.extraction_progress_bar.setValue(0)
        self.extraction_progress_bar.show()
        self.extraction_status_label.setText(f"Processing queue ({mode})...")
        self.extraction_status_label.show()

        # Deferred gallery paths for this run (see _on_queue_item_completed).
        self._queue_pending_gallery_paths = []

        self._queue_total_count = len(self.inprocess_items)
        self._queue_completed_count = 0
        self._current_queue_item_title = ""

        # Pass a COPY of the in-process batch: the worker iterates its own
        # list, and item_completed(index, ...) indexes back into this same
        # ordering to update per-item status.
        worker = QueueExecutionWorker(
            list(self.inprocess_items),
            parallel=is_parallel,
            max_workers=(
                getattr(self, "parallel_extraction_processors", None)
                if is_parallel
                else None
            ),
        )
        self.active_queue_worker = worker
        # Bind each connection to THIS worker so a late signal from a
        # previously cancelled run can't stomp the current one (or restart a
        # dead run). The handlers ignore any call whose worker is not current.
        worker.signals.progress.connect(
            lambda c, t, w=worker: self._on_queue_progress(c, t, w)
        )
        worker.signals.item_completed.connect(
            lambda i, r, it, w=worker: self._on_queue_item_completed(i, r, it, w)
        )
        worker.signals.finished.connect(
            lambda res, w=worker: self._on_queue_processing_finished(res, w)
        )
        worker.signals.error.connect(
            lambda msg, w=worker: self._on_queue_processing_error(msg, w)
        )

        self.operation_thread_pool.start(worker)

    @Slot(int, int)
    def _on_queue_progress(self: "VideoExtractorSubTabHostProtocol", completed: int, total: int, worker=None):
        if worker is not None and worker is not self.active_queue_worker:
            return
        self._queue_completed_count = completed
        self._queue_total_count = max(total, getattr(self, "_queue_total_count", total))
        self.extraction_progress_bar.setMaximum(max(total, 1))
        self.extraction_progress_bar.setValue(completed)

        # Advance the In Process list's per-item status.
        if self._inprocess_status:
            if worker is not None and not getattr(worker, "parallel", False):
                # Sequential: progress(i, total) fires as item i starts.
                if (
                    0 <= completed < len(self._inprocess_status)
                    and self._inprocess_status[completed] == _ST_PENDING
                ):
                    self._inprocess_status[completed] = _ST_PROCESSING
            else:
                # Parallel: the pool runs several items at once with no
                # per-item start signal — show every not-yet-finished item as
                # running; exact done/failed states arrive with item_completed.
                for j, st in enumerate(self._inprocess_status):
                    if st == _ST_PENDING:
                        self._inprocess_status[j] = _ST_PROCESSING
            self._update_inprocess_ui()

        if getattr(self, "_close_progress_dialog", None):
            self._close_progress_dialog.update_progress(
                completed,
                self._queue_total_count,
                getattr(self, "_current_queue_item_title", ""),
            )

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
        saved_metadata = item.get("history_metadata")
        if isinstance(saved_metadata, dict) and saved_metadata.get("video_path"):
            return copy.deepcopy(saved_metadata)

        # Defensive (Unknown Video bug): an empty/corrupt item cannot be
        # recorded faithfully. Fall back to the live UI state so a real
        # extraction is never recorded as "Unknown Video", and log the empty
        # item + stack so the real root cause can be pinned on reproduction.
        if not item.get("video_path"):
            import traceback

            print(
                f"[recent-extractions] EMPTY queue item at completion: item={item!r}",
                flush=True,
            )
            traceback.print_stack(limit=20)
            fallback = self._get_current_extraction_metadata()
            fallback["mode"] = item.get("type", "range")
            return fallback
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
    def _on_queue_item_completed(self: "VideoExtractorSubTabHostProtocol", index: int, res: dict, item: dict, worker=None):
        if worker is not None and worker is not self.active_queue_worker:
            return
        """Per-item completion: mark the item's status in the In Process list
        and record the extraction into recent extractions (queue results were
        previously never recorded there).

        `index` is the item's position in the batch handed to the worker,
        which is exactly self.inprocess_items' ordering — the parent-side
        config object is passed straight back (only the child's copy is
        pickled), so the index is reliable in both sequential and parallel
        modes.

        The gallery update is DEFERRED to _on_queue_processing_finished (or
        _on_queue_processing_error): rebuilding the gallery per item runs
        refresh_gallery_view() -> cancel_loading() -> thread_pool.
        waitForDone(-1) on the UI thread. Queue workers run on the separate
        operation_thread_pool; paths are accumulated and one rebuild happens
        once the worker is done.
        """
        # Per-item status for the right-hand list.
        if 0 <= index < len(self._inprocess_status):
            self._inprocess_status[index] = (
                _ST_DONE if res.get("status") == "success" else _ST_ERROR
            )
            self._update_inprocess_ui()

        paths = self._queue_result_paths(res)
        if not paths:
            return

        # Record first (so a failure below doesn't drop the history entry)
        metadata = self._queue_result_metadata(item)
        metadata["mode"] = item.get("type", "range")
        self._record_extraction(paths, metadata)

        # Defer the gallery update: see docstring above. Existence filtering
        # still happens here so a phantom path never enters the pending list.
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

    def _on_queue_processing_finished(self: "VideoExtractorSubTabHostProtocol", results, worker=None):
        if worker is not None and worker is not self.active_queue_worker:
            return
        self.active_queue_worker = None
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()

        # Resolve any item still shown as pending/processing from the final
        # results burst (parallel mode), then keep the In Process list on
        # screen until the user acknowledges the completion dialog.
        self._finalize_inprocess_from_results(results)

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

        all_paths = deferred + [p for p in new_paths if p not in deferred]
        if all_paths:
            self._add_queue_results_to_gallery(all_paths)

        close_dialog = getattr(self, "_close_progress_dialog", None)
        is_closing = close_dialog is not None or getattr(self, "_close_when_finished", None) is not None
        if close_dialog is not None:
            close_dialog.on_all_finished()
            self._clear_inprocess()  # headless close: no one to confirm
        elif is_closing:
            self._clear_inprocess()  # deferred close: suppress popup, clear now
        else:
            # Keep the In Process list on screen (with final per-item states)
            # until the user clicks OK — only then is it cleared.
            self._inprocess_awaiting_confirm = True
            self._set_queue_processing_state(False)
            if errors:
                QMessageBox.warning(
                    cast(QWidget, self),
                    "Queue Extraction Completed with Errors",
                    f"Processed {len(self.inprocess_items)} queue item(s). "
                    f"{len(errors)} error(s):\n" + "\n".join(errors)
                    + "\n\nClick OK to clear the In Process queue.",
                )
            else:
                QMessageBox.information(
                    cast(QWidget, self),
                    "Extractions Completed",
                    f"Queue execution complete — processed all "
                    f"{len(self.inprocess_items)} item(s), extracted {len(all_paths)} file(s)."
                    "\n\nClick OK to clear the In Process queue.",
                )
            self._clear_inprocess()

        self._maybe_finish_close()

    def _on_queue_processing_error(self: "VideoExtractorSubTabHostProtocol", error_msg, worker=None):
        if worker is not None and worker is not self.active_queue_worker:
            return
        self.active_queue_worker = None
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()

        # Whatever hadn't reported yet failed with the run.
        for j, st in enumerate(self._inprocess_status):
            if st in (_ST_PENDING, _ST_PROCESSING):
                self._inprocess_status[j] = _ST_ERROR
        self._update_inprocess_ui()

        close_dialog = getattr(self, "_close_progress_dialog", None)
        if close_dialog is not None:
            close_dialog.reject()

        # Flush any per-item results that completed before the failure so
        # they still appear in the gallery.
        if self._queue_pending_gallery_paths:
            self._add_queue_results_to_gallery(self._queue_pending_gallery_paths)
            self._queue_pending_gallery_paths = []

        cancelled = "cancelled" in error_msg.lower()
        if close_dialog is not None or getattr(self, "_close_when_finished", None) is not None:
            self._clear_inprocess()  # closing: nobody to confirm
        elif cancelled:
            # cancel_queue() already handled the UI reset and re-queue.
            self._clear_inprocess()
        else:
            self._inprocess_awaiting_confirm = True
            self._set_queue_processing_state(False)
            QMessageBox.warning(
                cast(QWidget, self),
                "Queue Processing Error",
                f"{error_msg}\n\nClick OK to clear the In Process queue.",
            )
            self._clear_inprocess()

        self._maybe_finish_close()

    def _prompt_inprocess_confirm(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Re-entry path: Process Queue was clicked while a finished batch is
        still awaiting acknowledgement. Confirm and clear it."""
        QMessageBox.information(
            cast(QWidget, self),
            "Extractions Completed",
            "The previous batch has finished. Click OK to clear the "
            "In Process queue, then press Process Queue again.",
        )
        self._clear_inprocess()

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

    def get_tasks_progress(self: "VideoExtractorSubTabHostProtocol") -> Tuple[int, int, str]:
        """Return (completed_count, total_count, current_item_title) for active extraction operations."""
        if getattr(self, "active_queue_worker", None) is not None:
            total = getattr(
                self,
                "_queue_total_count",
                max(self.extraction_progress_bar.maximum(), len(self.extraction_queue)),
            )
            completed = getattr(
                self,
                "_queue_completed_count",
                self.extraction_progress_bar.value(),
            )
            title = getattr(self, "_current_queue_item_title", "")
            return (completed, max(total, 1), title)
        elif getattr(self, "active_extraction_worker", None) is not None:
            val = self.extraction_progress_bar.value()
            max_val = max(self.extraction_progress_bar.maximum(), 100)
            title = Path(getattr(self, "video_path", "") or "").name
            return (val, max_val, title)
        return (0, 1, "")


__all__ = ["_QueueManagementMixin"]
