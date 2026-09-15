"""#484: per-child peak RSS self-calibration feeding #483's RAM estimate."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
from gui.src.helpers.core import _worker_rss_calibration as cal

pytestmark = pytest.mark.gui

_MOD_PATH = (
    Path(__file__).resolve().parents[2]
    / "src/components/widgets/resource_simulator_dashboard.py"
)


def _load_dashboard():
    spec = importlib.util.spec_from_file_location("_rsd_cal_under_test", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ResourceSimulatorDashboard


@pytest.fixture(autouse=True)
def _clean_calibration():
    cal.clear()
    yield
    cal.clear()


def test_empty_window_falls_back_to_static_floor():
    assert cal.effective_per_worker_mib() == cal.STATIC_FLOOR_MIB == 4096


def test_observed_peak_above_floor_wins():
    cal.record_run_peak_mb(6144.0, workers=2)
    assert cal.effective_per_worker_mib() == 6144


def test_small_observation_does_not_lower_estimate():
    # Upward-only: a 200 MiB test clip must not talk the simulator into
    # allowing more workers than the validated 4 GiB floor.
    cal.record_run_peak_mb(200.0, workers=1)
    assert cal.effective_per_worker_mib() == 4096


def test_rolling_max_keeps_largest_and_ages_out():
    cal.record_run_peak_mb(5000.0, workers=2)
    cal.record_run_peak_mb(4500.0, workers=2)
    assert cal.effective_per_worker_mib() == 5000
    for _ in range(cal.WINDOW):
        cal.record_run_peak_mb(4200.0, workers=2)
    assert cal.effective_per_worker_mib() == 4200
    assert len(cal.run_peak_samples()) == cal.WINDOW


def test_invalid_records_ignored():
    cal.record_run_peak_mb(0.0, workers=2)
    cal.record_run_peak_mb(-5.0, workers=2)
    cal.record_run_peak_mb(9000.0, workers=0)
    assert cal.run_peak_samples() == []
    assert cal.effective_per_worker_mib() == 4096


def test_run_peak_from_results_takes_max_and_ignores_gaps():
    results = [
        {"status": "success", "worker_peak_rss_mb": 4100.5},
        {"status": "success", "worker_peak_rss_mb": 4600.0},
        {"status": "error", "message": "boom"},  # failed before stamping
        "not-a-dict",
        {"status": "success", "worker_peak_rss_mb": -3},
        {"status": "success", "worker_peak_rss_mb": "huge"},
    ]
    assert cal.run_peak_from_results(results) == 4600.0
    assert cal.run_peak_from_results([]) is None
    assert cal.run_peak_from_results(None) is None
    assert cal.run_peak_from_results([{"status": "error"}]) is None


def test_extraction_result_carries_child_peak_stamp():
    """The wrapper stamps the calling process's own peak (same mechanism
    the spawn child uses — here exercised in-process with mocked ffmpeg)."""
    from gui.src.helpers.core._queue_extraction_process import run_extraction_in_process

    config = {
        "type": "gif",
        "video_path": "/tmp/never_read.mp4",
        "start_ms": 0,
        "end_ms": 1000,
        "output_dir": "/tmp",
        "fps": 60,
        "encoder_threads": 4,
        "max_colors": 64,
        "fps_clamp": 24,
        "use_ffmpeg": True,
    }
    with patch("subprocess.run") as mock_run:
        res = run_extraction_in_process(config)
    assert res.get("status") == "success"
    assert mock_run.call_count == 2
    assert res.get("worker_peak_rss_mb", 0) > 0


def test_parallel_run_records_child_peaks(q_app, tmp_path):
    """Full chain with a real spawn pool: children stamp, parent aggregates,
    registry records one run peak. Dummy video fails fast in the child —
    error dicts are stamped too, so even this calibrates the mechanism
    (not the workload)."""
    from gui.src.helpers.core.queue_execution_worker import QueueExecutionWorker

    items = [
        {"type": "gif", "video_path": "dummy", "start_ms": 0, "end_ms": 500},
        {"type": "gif", "video_path": "dummy", "start_ms": 500, "end_ms": 1000},
    ]
    worker = QueueExecutionWorker(items, parallel=True, max_workers=2)
    worker.run()
    samples = cal.run_peak_samples()
    assert len(samples) == 1
    assert samples[0] > 0


def test_dashboard_prefers_calibrated_value(q_app):
    RSD = _load_dashboard()
    d = RSD()
    cal.record_run_peak_mb(6144.0, workers=2)
    try:
        d.update_simulation(enabled=True, workers=2)
        assert "6.0 GiB/ea" in d.card_workers.subtext_label.text()
    finally:
        cal.clear()
    d.update_simulation(enabled=True, workers=2)
    assert "4.0 GiB/ea" in d.card_workers.subtext_label.text()


def test_explicit_override_still_wins(q_app):
    RSD = _load_dashboard()
    d = RSD()
    cal.record_run_peak_mb(6144.0, workers=2)
    try:
        d.update_simulation(enabled=True, workers=2, per_worker_mib=2048)
        assert "2.0 GiB/ea" in d.card_workers.subtext_label.text()
    finally:
        cal.clear()
