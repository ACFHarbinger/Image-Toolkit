"""Cancelling the extraction queue must not wedge a later Process Queue click."""

from __future__ import annotations

import pytest

from gui.src.tabs.core.extractor_tab._queue_management import (
    ExtractorQueueManagementController,
)
from PySide6.QtWidgets import QComboBox, QPushButton

pytestmark = pytest.mark.gui


class _Label:
    def setText(self, *_):
        ...

    def show(self):
        ...

    def hide(self):
        ...

    def setMaximum(self, *_):
        ...

    def setValue(self, *_):
        ...


class _Host:
    """Minimal façade matching VideoExtractorSubTab's composed contract."""

    def __init__(self):
        self.active_queue_worker = object()
        self.extraction_status_label = _Label()
        self.extraction_progress_bar = _Label()
        self.extraction_queue = []
        self.inprocess_items = []
        self._inprocess_status = []
        self._inprocess_awaiting_confirm = False
        self._state = None
        self.btn_clear_queue = QPushButton()
        self.btn_process_queue = QPushButton()
        self.combo_queue_mode = QComboBox()
        self._ctrl = ExtractorQueueManagementController(self)
        # Instance attribute so TabBoundController prefers this façade
        # over the controller method (same contract as the real subtab).
        self._set_queue_processing_state = self._record_processing_state

    def _record_processing_state(self, processing):
        self._state = processing

    def _update_inprocess_ui(self):
        ...

    def _update_queue_ui(self):
        ...

    def cancel_queue(self):
        return self._ctrl.cancel_queue()

    def _on_queue_processing_finished(self, *args, **kwargs):
        return self._ctrl._on_queue_processing_finished(*args, **kwargs)

    def _on_queue_progress(self, *args, **kwargs):
        return self._ctrl._on_queue_progress(*args, **kwargs)

    def _on_queue_item_completed(self, *args, **kwargs):
        return self._ctrl._on_queue_item_completed(*args, **kwargs)


def test_cancel_queue_nulls_worker_immediately():
    h = _Host()
    h.cancel_queue()
    assert h.active_queue_worker is None
    assert h._state is False


def test_stale_finished_signal_is_ignored_after_cancel():
    h = _Host()
    stale = h.active_queue_worker
    h.cancel_queue()
    new_worker = object()
    h.active_queue_worker = new_worker
    h._on_queue_processing_finished([], worker=stale)
    assert h.active_queue_worker is new_worker


def test_progress_and_item_completed_ignore_stale_worker():
    h = _Host()
    current = object()
    h.active_queue_worker = current
    h._on_queue_progress(1, 2, worker=object())
    h._on_queue_item_completed(0, {}, {}, worker=object())
    assert h.active_queue_worker is current
