"""Tests for the shared extraction pipeline (ui-arch-41 / #563, R2.a).

Covers the previously inline, untested mechanics now shared by the
frame/gif/video extractor workers and the queue execution worker:
keep-region merging, quiet/progress ffmpeg runs, failure text, and
cancellation.
"""

from __future__ import annotations

import sys

import pytest
from gui.src.helpers.video.extraction_pipeline import (
    ExtractionCancelled,
    _ffmpeg_thread_count,
    get_keep_regions,
    parse_ffmpeg_progress_line,
    run_ffmpeg,
)


def test_keep_regions_no_cuts():
    assert get_keep_regions([], 2.0, 7.0) == [(0.0, 5.0)]
    assert get_keep_regions(None, 0.0, 3.0) == [(0.0, 3.0)]


def test_keep_regions_merges_overlaps_and_skips_degenerate():
    cuts = [[1000, 3000], [2000, 4000], [5000, 5000], [9000, 8000]]
    assert get_keep_regions(cuts, 0.0, 10.0) == [(0.0, 1.0), (4.0, 10.0)]


def test_keep_regions_exact_cut_keeps_nothing():
    assert get_keep_regions([[0, 5000]], 0.0, 5.0) == []


def test_thread_count_bounds():
    import os

    cpus = os.cpu_count() or 2
    assert 1 <= _ffmpeg_thread_count(0) <= min(4, cpus)
    assert _ffmpeg_thread_count(999) == cpus


def test_progress_line_mapping():
    assert parse_ffmpeg_progress_line("out_time_us=500000", 2.0) == 25
    assert parse_ffmpeg_progress_line("out_time_us=N/A", 2.0) is None


def test_run_ffmpeg_quiet_success(tmp_path):
    out = tmp_path / "out.txt"
    run_ffmpeg(
        [sys.executable, "-c", f"open({str(out)!r}, 'w').write('ok')"],
        "boom ",
        is_cancelled=lambda: False,
    )
    assert out.read_text() == "ok"


def test_run_ffmpeg_failure_text():
    with pytest.raises(RuntimeError) as ei:
        run_ffmpeg(
            [sys.executable, "-c", "import sys;sys.stderr.write('tail-text');sys.exit(3)"],
            "ffmpeg palette pass failed (code ",
        )
    assert "ffmpeg palette pass failed (code 3" in str(ei.value)
    assert "tail-text" in str(ei.value)


def test_run_ffmpeg_precancelled_raises():
    with pytest.raises(ExtractionCancelled):
        run_ffmpeg(
            [sys.executable, "-c", "import time;time.sleep(30)"],
            "FFmpeg failed with return code ",
            is_cancelled=lambda: True,
        )


def test_run_ffmpeg_progress_mode():
    seen = []
    script = "import sys\nprint('out_time_us=500000', flush=True)\nprint('progress=end', flush=True)\n"
    run_ffmpeg(
        [sys.executable, "-c", script],
        "FFmpeg failed with return code ",
        duration_s=2.0,
        progress=lambda a, b: seen.append((a, b)),
    )
    assert (25, 100) in seen
