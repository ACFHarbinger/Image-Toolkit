"""Unit tests for TaskCloseProgressDialog and queue cancel/process button controls."""

from __future__ import annotations

from unittest.mock import MagicMock

from gui.src.components.dialogs.extraction_close_progress_dialog import (
    TaskCloseProgressDialog,
)
from gui.src.tabs.core.extractor_tab._queue_management import (
    _QueueManagementMixin,
)


class DummyQueueHost(_QueueManagementMixin):
    def __init__(self):
        self.btn_process_queue = MagicMock()
        self.btn_clear_queue = MagicMock()
        self.combo_queue_mode = MagicMock()
        self.queue_list = MagicMock()
        self.extraction_progress_bar = MagicMock()
        self.extraction_status_label = MagicMock()
        self.active_queue_worker = None
        self.extraction_queue = []
        self.inprocess_items = []
        self._inprocess_status = []
        self._inprocess_awaiting_confirm = False
        self._close_progress_dialog = None


def test_task_close_progress_dialog_lifecycle(q_app):
    cancel_mock = MagicMock()
    confirm_mock = MagicMock()

    dlg = TaskCloseProgressDialog(
        parent=None,
        on_cancel=cancel_mock,
        on_confirm=confirm_mock,
        total=5,
        completed=1,
    )

    assert dlg.windowTitle() == "Tasks in Progress"
    assert "Tasks in Progress" in dlg.lbl_header.text()
    assert dlg.progress_bar.maximum() == 5
    assert dlg.progress_bar.value() == 1
    assert not dlg.btn_ok.isEnabled()
    assert dlg.btn_cancel.isEnabled()
    assert dlg.btn_cancel.text() == "Cancel Tasks"

    # Progress update
    dlg.update_progress(completed=3, total=5, item_title="video_03.mkv")
    assert dlg.progress_bar.value() == 3
    assert "video_03.mkv" in dlg.lbl_status.text()
    assert not dlg.btn_ok.isEnabled()

    # Finished
    dlg.on_all_finished()
    assert dlg.progress_bar.value() == 5
    assert dlg.btn_ok.isEnabled()
    assert not dlg.btn_cancel.isEnabled()
    assert "Tasks Complete" in dlg.lbl_header.text()

    # Confirm action
    dlg._handle_confirm()
    confirm_mock.assert_called_once()


def test_task_close_progress_dialog_cancel(q_app):
    cancel_mock = MagicMock()
    confirm_mock = MagicMock()

    dlg = TaskCloseProgressDialog(
        parent=None,
        on_cancel=cancel_mock,
        on_confirm=confirm_mock,
        total=3,
        completed=0,
    )

    dlg._handle_cancel()
    cancel_mock.assert_called_once()
    confirm_mock.assert_not_called()


def test_queue_processing_state_toggle():
    host = DummyQueueHost()
    # The On Hold queue stays independently editable/clearable in every state,
    # so Clear Queue tracks the left queue's length regardless of processing.
    host.extraction_queue = [{"video_path": "x", "type": "range", "start_ms": 0, "end_ms": 1}]

    # State: Processing
    # pyrefly: ignore [bad-argument-type]
    host._set_queue_processing_state(True)
    # pyrefly: ignore [missing-attribute]
    host.btn_process_queue.setText.assert_called_with("🛑 Cancel Queue")
    # pyrefly: ignore [missing-attribute]
    host.btn_clear_queue.setEnabled.assert_called_with(True)  # left queue non-empty
    # pyrefly: ignore [missing-attribute]
    host.combo_queue_mode.setEnabled.assert_called_with(False)

    # State: Idle
    # pyrefly: ignore [bad-argument-type]
    host._set_queue_processing_state(False)
    # pyrefly: ignore [missing-attribute]
    host.btn_process_queue.setText.assert_called_with("⚙️ Process Queue")
    # pyrefly: ignore [missing-attribute]
    host.combo_queue_mode.setEnabled.assert_called_with(True)
    # pyrefly: ignore [missing-attribute]
    host.btn_process_queue.setEnabled.assert_called_with(True)  # has items, idle

    # State: awaiting confirmation of a finished batch -> Process stays dead
    host._inprocess_awaiting_confirm = True
    # pyrefly: ignore [bad-argument-type]
    host._set_queue_processing_state(False)
    # pyrefly: ignore [missing-attribute]
    host.btn_process_queue.setEnabled.assert_called_with(False)


def test_cancel_queue_invokes_worker_cancel():
    host = DummyQueueHost()
    worker_mock = MagicMock()
    host.active_queue_worker = worker_mock

    # pyrefly: ignore [bad-argument-type]
    host.cancel_queue()
    worker_mock.cancel.assert_called_once()
    # pyrefly: ignore [missing-attribute]
    host.btn_process_queue.setText.assert_called_with("⚙️ Process Queue")


def test_get_tasks_progress_reflects_active_queue_progress():
    host = DummyQueueHost()
    host.active_queue_worker = MagicMock()
    # pyrefly: ignore [missing-attribute]
    host.extraction_progress_bar = MagicMock()
    # pyrefly: ignore [missing-attribute]
    host.extraction_progress_bar.maximum.return_value = 27
    # pyrefly: ignore [missing-attribute]
    host.extraction_progress_bar.value.return_value = 17
    host._queue_total_count = 27
    host._queue_completed_count = 17
    host._current_queue_item_title = "episode_01.mkv"

    # pyrefly: ignore [bad-argument-type]
    completed, total, title = host.get_tasks_progress()
    assert completed == 17
    assert total == 27
    assert title == "episode_01.mkv"


def test_task_close_progress_dialog_initialized_with_partial_progress(q_app):
    dlg = TaskCloseProgressDialog(
        parent=None,
        total=27,
        completed=17,
    )

    assert dlg.progress_bar.maximum() == 27
    assert dlg.progress_bar.value() == 17
    assert dlg.lbl_status.text() == "Processed 17 of 27 tasks"

