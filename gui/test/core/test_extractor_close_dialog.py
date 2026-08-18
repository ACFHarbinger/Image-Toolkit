"""Unit tests for TaskCloseProgressDialog and queue cancel/process button controls."""

from __future__ import annotations

from unittest.mock import MagicMock

from gui.src.components.dialogs.extraction_close_progress_dialog import (
    TaskCloseProgressDialog,
)
from gui.src.elements.core.extractor_tab._queue_management import (
    _QueueManagementMixin,
)


class DummyQueueHost(_QueueManagementMixin):
    def __init__(self):
        self.btn_process_queue = MagicMock()
        self.btn_clear_queue = MagicMock()
        self.combo_queue_mode = MagicMock()
        self.active_queue_worker = None
        self.extraction_queue = []
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

    # State: Processing
    host._set_queue_processing_state(True)
    host.btn_process_queue.setText.assert_called_with("🛑 Cancel Queue")
    host.btn_clear_queue.setEnabled.assert_called_with(False)
    host.combo_queue_mode.setEnabled.assert_called_with(False)

    # State: Idle
    host._set_queue_processing_state(False)
    host.btn_process_queue.setText.assert_called_with("⚙️ Process Queue")
    host.btn_clear_queue.setEnabled.assert_called_with(True)
    host.combo_queue_mode.setEnabled.assert_called_with(True)


def test_cancel_queue_invokes_worker_cancel():
    host = DummyQueueHost()
    worker_mock = MagicMock()
    host.active_queue_worker = worker_mock

    host.cancel_queue()
    worker_mock.cancel.assert_called_once()
    host.btn_process_queue.setText.assert_called_with("⚙️ Process Queue")
