"""#742: reader-side loss curve. Raw JSONL is not rewritten."""
import math

from middleware.src.core.training_curve import (
    bucket_minmax,
    checkpoint_index,
    latest_epoch,
    loss_series,
    sample_file,
    smooth_series,
    step_at_ratio,
)


def test_loss_series_keeps_finite_points_and_sorts():
    events = [
        {"step": 3, "loss": 0.2},
        "nope",
        {"step": True, "loss": 1.0},
        {"step": 1, "loss": 0.5},
        {"step": 2},
        {"loss": 0.1},
        {"step": 4, "loss": math.nan},
        {"step": "5", "loss": "0.1"},
        {"step": 2.5, "loss": 0.3},
        {"step": 0, "loss": 1},
    ]
    assert loss_series(events) == [(0, 1.0), (1, 0.5), (3, 0.2), (5, 0.1)]


def test_smooth_is_a_trailing_mean_and_leaves_raw_alone():
    raw = [(1, 0.0), (2, 10.0), (3, 0.0)]
    assert smooth_series(raw, window=16)[1] == (2, 5.0)
    assert raw[1] == (2, 10.0)


def test_buckets_keep_a_one_step_spike():
    points = [(index, 0.1) for index in range(100)]
    points[50] = (50, 9.0)
    buckets = bucket_minmax(points, 10)
    assert any(high == 9.0 for _first, _last, _low, high in buckets)


def test_checkpoint_index_is_latest_at_or_before_cursor():
    steps = [10, 20, 40]
    assert checkpoint_index(steps, 25) == 1
    assert checkpoint_index(steps, 10) == 0
    assert checkpoint_index(steps, 5) is None
    assert checkpoint_index(steps, 40) == 2


def test_step_at_ratio_uses_the_series_ends():
    points = [(10, 1.0), (20, 0.5), (40, 0.2)]
    assert step_at_ratio(points, 0.0) == 10
    assert step_at_ratio(points, 1.0) == 40
    assert step_at_ratio([], 0.5) is None


def test_latest_epoch_ignores_missing_and_bool():
    events = [{"epoch": 1}, {"step": 2}, {"epoch": True}, {"epoch": 3}]
    assert latest_epoch(events) == 3
    assert latest_epoch([]) is None


def test_sample_file_rejects_paths_outside_the_run(tmp_path):
    assert sample_file(tmp_path, "samples/step-000001.png") == (tmp_path / "samples/step-000001.png").resolve()
    assert sample_file(tmp_path, "../etc/passwd") is None
    assert sample_file(tmp_path, "/etc/passwd") is None
    assert sample_file(tmp_path, "") is None
    assert sample_file(tmp_path, "samples/../../outside.png") is None
