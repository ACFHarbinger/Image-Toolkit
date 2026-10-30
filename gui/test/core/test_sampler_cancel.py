"""Cancelling a resample must not block the GUI thread or keep the job running."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from middleware.src.services.media.gif_upscale.base import ResampleCancelled

from gui.src.helpers.core.sampler_worker import SamplerWorker
from gui.src.tabs.core.sampler_subtab._resample_worker import SamplerWorkerController


def test_progress_callback_raises_once_cancelled():
    worker = SamplerWorker({})
    progress = worker._make_progress(0, 1)
    progress("scale", 1, 10)  # not cancelled: no effect
    worker.cancel()
    with pytest.raises(ResampleCancelled):
        progress("scale", 2, 10)


def test_cancelled_file_reports_false_instead_of_failing(tmp_path, monkeypatch):
    source = tmp_path / "clip.gif"
    source.write_bytes(b"GIF89a")
    worker = SamplerWorker({"algorithm": "nearest"})

    def fake_gif(_in, _out, progress):
        worker.cancel()
        progress("scale", 1, 2)  # raises ResampleCancelled
        return True

    monkeypatch.setattr(worker, "_resample_gif", fake_gif)
    # cancel() is called inside the fake, so the early `_is_cancelled` guard has not fired yet.
    assert worker._resample_one(str(source), 0, 1) is False


def test_second_click_cancels_without_waiting_on_the_gui_thread():
    worker = MagicMock()
    worker.isRunning.return_value = True
    button = MagicMock()
    tab = SimpleNamespace(
        worker=worker,
        btn_all=button,
        btn_selected=MagicMock(),
        status_label=MagicMock(),
    )
    SamplerWorkerController(tab)._start_worker(False)
    worker.cancel.assert_called_once()
    worker.wait.assert_not_called()
    button.setEnabled.assert_called_with(False)
    assert tab.worker is worker  # _on_done clears it when the thread finishes
