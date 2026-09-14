"""Extraction queue processing: run/cancel, progress, completion, close deferral.

Split from ``_queue_management`` (§5.17 Option B, #629) — pure code
motion, no logic change. Composed into
:class:`ExtractorQueueManagementController` together with
:mod:`_queue_panel`; cross-module calls resolve via ``self`` on the
leaf class at runtime.
"""

from __future__ import annotations

import contextlib
import copy
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

from ....components import ClickableLabel
from ....helpers.core.queue_execution_worker import QueueExecutionWorker
from ._queue_panel import _ST_DONE, _ST_ERROR, _ST_PENDING, _ST_PROCESSING
from ._tab_bound import TabBoundController

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class ExtractorQueueProcessingController(TabBoundController):
    """Queue run execution: cancel/process, progress, results, close deferral."""

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
        worker.signals.item_started.connect(
            lambda i, w=worker: self._on_queue_item_started(i, w)
        )
        worker.signals.item_completed.connect(
            lambda i, r, it, w=worker: self._on_queue_item_completed(i, r, it, w)
        )
        worker.signals.finished.connect(
            lambda res, w=worker: self._on_queue_processing_finished(res, w)
        )
        worker.signals.error.connect(
            lambda msg, w=worker: self._on_queue_processing_error(str(msg), w)
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

    @Slot(int)
    def _on_queue_item_started(self: "VideoExtractorSubTabHostProtocol", index: int, worker=None):
        if worker is not None and worker is not self.active_queue_worker:
            return
        if (
            0 <= index < len(self._inprocess_status)
            and self._inprocess_status[index] == _ST_PENDING
        ):
            self._inprocess_status[index] = _ST_PROCESSING
            self._update_inprocess_ui()

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
        if results is None:  # failure/cancel — error path already reported
            return

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
                    self.tab,
                    "Queue Extraction Completed with Errors",
                    f"Processed {len(self.inprocess_items)} queue item(s). "
                    f"{len(errors)} error(s):\n" + "\n".join(errors)
                    + "\n\nClick OK to clear the In Process queue.",
                )
            else:
                QMessageBox.information(
                    self.tab,
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
                self.tab,
                "Queue Processing Error",
                f"{error_msg}\n\nClick OK to clear the In Process queue.",
            )
            self._clear_inprocess()

        self._maybe_finish_close()

    def _prompt_inprocess_confirm(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Re-entry path: Process Queue was clicked while a finished batch is
        still awaiting acknowledgement. Confirm and clear it."""
        QMessageBox.information(
            self.tab,
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


__all__ = ["ExtractorQueueProcessingController"]
