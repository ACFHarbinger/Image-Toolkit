"""Extraction queue panel: results-section build, queue CRUD, In Process list UI.

Split from ``_queue_management`` (§5.17 Option B, #629) — pure code
motion, no logic change. Composed into
:class:`ExtractorQueueManagementController` together with
:mod:`_queue_processing`; cross-module calls resolve via ``self`` on the
leaf class at runtime.
"""

from __future__ import annotations

import copy
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

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
)

from ....components import VirtualGallery
from ....helpers import ImageLoaderWorker, VideoLoaderWorker
from ....styles import set_button_role
from ....theming.theme_api import qss
from ._tab_bound import TabBoundController

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


def retarget_pending_queue_items(queue: list, new_dir) -> int:
    """Point not-yet-started (On Hold) queue items at ``new_dir``.

    Items snapshot ``output_dir`` when enqueued, so without this a directory
    change made afterwards still writes to the old folder. In-process items
    are already running against their snapshot and are deliberately left
    alone. Returns how many items changed.
    """
    target = str(new_dir)
    changed = 0
    for item in queue:
        if item.get("output_dir") != target:
            item["output_dir"] = target
            changed += 1
    return changed


class ExtractorQueuePanelController(TabBoundController):
    """Queue panel UI: results section, list CRUD, In Process display."""

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

        self.gallery = VirtualGallery(self.tab, worker_factory=_gallery_worker)
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
        self.extraction_status_label.setStyleSheet(qss("status_label_padded"))
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

        menu = QMenu(self.tab)
        menu.setStyleSheet(qss("extractor_menu"))
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
                self.tab, "File Not Found", f"The video file '{v_path}' no longer exists."
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


__all__ = [
    "ExtractorQueuePanelController",
    "_ST_DONE",
    "_ST_ERROR",
    "_ST_PENDING",
    "_ST_PROCESSING",
    "_inprocess_row_label",
]
