"""Cancelling the extraction queue must not wedge a later Process Queue click."""

from __future__ import annotations

import pytest

from gui.src.tabs.core.extractor_tab._queue_management import _QueueManagementMixin

pytestmark = pytest.mark.gui


class _Label:
    def setText(self, *_):
        ...

    def show(self):
        ...

    def hide(self):
        ...


class _Host(_QueueManagementMixin):
    def __init__(self):
        self.active_queue_worker = object()
        self.extraction_status_label = _Label()
        self.extraction_progress_bar = _Label()
        self._state = None

    def _set_queue_processing_state(self, processing):
        self._state = processing


def test_cancel_queue_nulls_worker_immediately():
    h = _Host()
    h.cancel_queue()
    assert h.active_queue_worker is None
    assert h._state is False


def test_stale_finished_signal_is_ignored_after_cancel():
    h = _Host()
    stale = h.active_queue_worker
    h.cancel_queue()
    # a NEW run is now active
    new_worker = object()
    h.active_queue_worker = new_worker
    # the cancelled worker's late 'finished' must not clear the new run
    h._on_queue_processing_finished([], worker=stale)
    assert h.active_queue_worker is new_worker


def test_progress_and_item_completed_ignore_stale_worker():
    h = _Host()
    current = object()
    h.active_queue_worker = current
    h._on_queue_progress(1, 2, worker=object())     # stale -> no crash, no-op
    h._on_queue_item_completed(0, {}, {}, worker=object())
    assert h.active_queue_worker is current
