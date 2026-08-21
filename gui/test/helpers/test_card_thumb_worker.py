from __future__ import annotations

import pytest
from gui.src.helpers.image import card_thumb_worker
from PySide6.QtWidgets import QLabel

pytestmark = pytest.mark.gui


class _FakeSignal:
    def connect(self, callback):
        self.callback = callback


class _FakeWorker:
    def __init__(self, paths, target_size):
        self.paths = paths
        self.target_size = target_size
        self.signals = type("Signals", (), {"batch_result": _FakeSignal()})()


class _FakePool:
    def __init__(self):
        self.started = []

    def start(self, worker):
        self.started.append(worker)


def test_card_requests_are_coalesced_into_one_batch(q_app, monkeypatch):
    pool = _FakePool()
    monkeypatch.setattr(card_thumb_worker, "BatchImageLoaderWorker", _FakeWorker)
    monkeypatch.setattr(
        card_thumb_worker.QThreadPool, "globalInstance", lambda: pool
    )
    card_thumb_worker._PENDING_THUMBS.clear()
    card_thumb_worker._INFLIGHT_PATHS.clear()
    card_thumb_worker._BATCH_FLUSH_SCHEDULED = False

    first = QLabel()
    second = QLabel()
    card_thumb_worker._queue_thumbnail_load("one.png", first, 80, 80, 128)
    card_thumb_worker._queue_thumbnail_load("two.png", second, 80, 80, 128)
    card_thumb_worker._flush_thumbnail_batch()

    assert len(pool.started) == 1
    assert set(pool.started[0].paths) == {"one.png", "two.png"}
    assert pool.started[0].target_size == 128
