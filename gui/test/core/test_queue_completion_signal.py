"""Issue #633: parallel queue reaches N/N done but the completion dialog never fires.

Stress harness driving the REAL `process_queue` path (real tab, real
`QueueExecutionWorker` on the real `operation_thread_pool`, stubbed
per-item extraction fn producing real files) with a recording
`QMessageBox`, counting completion dialogs across repeated batches and
cancel/restart overlap. A lost `finished` wedges the queue exactly as
the issue describes: header shows N/N (all `item_completed` delivered)
but no dialog, `active_queue_worker` never cleared.
"""

from __future__ import annotations

import gc
import time
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.gui

BATCH_ITEMS = 6
BATCH_TIMEOUT_S = 90.0


def _fast_fake_extract(item):
    """Stand-in for `run_extraction_in_process`: fast, picklable, succeeding.

    Returns the item's own `output_path` so results look exactly like a
    real successful extraction downstream (gallery/history paths run).
    """
    import time as _t

    _t.sleep(0.01)
    return {"status": "success", "output_path": item.get("output_path", "")}


class _DialogRecorder:
    def __init__(self):
        self.calls = []

    def information(self, *args):
        self.calls.append(("information", args[1] if len(args) > 1 else ""))
        from PySide6.QtWidgets import QMessageBox

        return QMessageBox.StandardButton.Ok

    def warning(self, *args):
        self.calls.append(("warning", args[1] if len(args) > 1 else ""))
        from PySide6.QtWidgets import QMessageBox

        return QMessageBox.StandardButton.Ok

    def question(self, *args):
        self.calls.append(("question", ""))
        from PySide6.QtWidgets import QMessageBox

        return QMessageBox.StandardButton.Yes


def _make_tab(tmp_path):
    from gui.src.tabs.core.extractor_tab import ExtractorTab

    video_path = tmp_path / "episode.mp4"
    video_path.write_text("dummy")
    with (
        patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
        patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
    ):
        tab = ExtractorTab()
    tab.video_path = str(video_path)
    tab.extraction_dir = tmp_path / "out"
    tab.extraction_dir.mkdir(exist_ok=True)
    tab.parallel_extraction_processors = 2
    return tab


def _pump_until(cond, timeout_s=BATCH_TIMEOUT_S):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    QApplication.processEvents()
    return cond()


def _fill_and_process(tab, n=BATCH_ITEMS):
    for i in range(n):
        out = tab.extraction_dir / f"q633_{time.monotonic_ns()}_{i}.gif"
        out.write_text("gif")
        tab.extraction_queue.append(
            {"type": "gif", "video_path": "dummy", "start_ms": i * 1000,
             "end_ms": (i + 1) * 1000, "output_path": str(out)}
        )
    tab.combo_queue_mode.setCurrentText("Parallel (Multiprocessing)")
    tab.process_queue()


def _completed_dialogs(recorder):
    return [c for c in recorder.calls if c[0] == "information" and "Completed" in c[1]]


class TestQueueCompletionSignal:
    def _patched(self, tab):
        return (
            patch(
                "gui.src.helpers.core.queue_execution_worker.run_extraction_in_process",
                _fast_fake_extract,
            ),
            patch(
                "gui.src.tabs.core.extractor_tab._queue_processing.QMessageBox",
                _DialogRecorder(),
            ),
            patch.object(tab.video_subtab, "start_loading_gallery", return_value=None),
        )

    def test_repeated_parallel_batches_all_show_completion(self, q_app, tmp_path):
        """Back-to-back parallel batches: every run must end in exactly one
        completion dialog with the worker reference cleared (issue #633)."""
        tab = _make_tab(tmp_path)
        fake, msgbox, gallery = self._patched(tab)
        recorder = msgbox.new
        rounds = 6
        with fake, msgbox, gallery:
            for _ in range(rounds):
                before = len(_completed_dialogs(recorder))
                _fill_and_process(tab)
                ok = _pump_until(lambda b=before: len(_completed_dialogs(recorder)) > b)
                assert ok, "completion dialog never fired for a parallel batch (#633)"
                assert tab.active_queue_worker is None
                assert tab.inprocess_items == []
        assert len(_completed_dialogs(recorder)) == rounds

    def test_finished_survives_ref_drop_and_gc_mid_run(self, q_app, tmp_path):
        """Suspect #1: dropping every external worker reference and forcing
        cyclic collection mid-run must not lose `finished` (#633).

        Regression: `_RUNNING_WORKERS` used to discard at `_execute()`
        return — before `finished.emit` — so a teardown-dropped worker
        could be collected with its queued delivery still pending, and
        PySide drops the delivery. The guard now releases at delivery.
        """
        from PySide6.QtCore import QThreadPool

        from gui.src.helpers.core.queue_execution_worker import (
            _RUNNING_WORKERS,
            QueueExecutionWorker,
        )

        pool = QThreadPool()
        pool.setMaxThreadCount(2)
        try:
            with patch(
                "gui.src.helpers.core.queue_execution_worker.run_extraction_in_process",
                _fast_fake_extract,
            ):
                for _ in range(5):
                    items = [
                        {"type": "gif", "video_path": "dummy", "output_path": ""}
                        for _ in range(4)
                    ]
                    worker = QueueExecutionWorker(items, parallel=True, max_workers=2)
                    wid = id(worker)
                    state = {"items": 0, "finished": 0}
                    worker.signals.item_completed.connect(
                        lambda i, r, it, s=state: s.__setitem__("items", s["items"] + 1)
                    )
                    worker.signals.finished.connect(
                        lambda res, s=state: s.__setitem__("finished", s["finished"] + 1)
                    )
                    pool.start(worker)
                    # Simulate a mid-run tab teardown: drop every external
                    # reference and force cyclic collection while the pool
                    # thread is still working.
                    del worker
                    for _ in range(20):
                        gc.collect()
                        QApplication.processEvents()
                        if state["finished"]:
                            break
                        time.sleep(0.05)
                    assert state["items"] == 4
                    assert _pump_until(
                        lambda s=state: s["finished"] == 1, timeout_s=60.0
                    ), "finished lost after mid-run ref drop + gc (#633)"
                    # The delivery-time guard must have released the worker.
                    assert wid not in {id(w) for w in _RUNNING_WORKERS}
        finally:
            pool.waitForDone(30000)

    def test_cancel_restart_overlap_finishes_cleanly(self, q_app, tmp_path):
        """Cancel mid-run then immediately restart: the stale run's late
        signals must be ignored and the new run must complete with a dialog."""
        tab = _make_tab(tmp_path)
        fake, msgbox, gallery = self._patched(tab)
        recorder = msgbox.new
        with fake, msgbox, gallery:
            _fill_and_process(tab)
            _pump_until(lambda: tab._queue_completed_count > 0, timeout_s=30.0)
            tab.cancel_queue()
            _fill_and_process(tab)
            ok = _pump_until(lambda: len(_completed_dialogs(recorder)) > 0)
            assert ok, "restarted batch never showed its completion dialog"
            assert tab.active_queue_worker is None
