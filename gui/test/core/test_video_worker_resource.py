"""#484: video extractor ffmpeg run — no stderr-PIPE deadlock, thread cap, progress."""

from __future__ import annotations

import os
import sys

import pytest

from gui.src.helpers.video.video_extractor_worker import (
    VideoExtractionWorker,
    _Cancelled,
    _ffmpeg_thread_count,
    parse_ffmpeg_progress_line,
)


def _worker(tmp_path, **kw):
    return VideoExtractionWorker(
        video_path=str(tmp_path / "v.mp4"),
        start_ms=0,
        end_ms=2000,
        output_path=str(tmp_path / "out.mp4"),
        use_ffmpeg=True,
        **kw,
    )


def test_run_ffmpeg_does_not_deadlock_on_large_stderr(q_app, tmp_path):
    w = _worker(tmp_path)
    flood = "import sys; sys.stderr.write('x' * 500_000); sys.stderr.flush()"
    w._run_ffmpeg([sys.executable, "-c", flood], duration_s=2.0)


def test_run_ffmpeg_reports_failure_with_stderr_tail(q_app, tmp_path):
    w = _worker(tmp_path)
    with pytest.raises(RuntimeError) as ei:
        w._run_ffmpeg(
            [sys.executable, "-c", "import sys;sys.stderr.write('boom');sys.exit(2)"],
            duration_s=2.0,
        )
    assert "boom" in str(ei.value) and "return code 2" in str(ei.value)


def test_run_ffmpeg_cancel_raises(q_app, tmp_path):
    w = _worker(tmp_path)
    w._is_cancelled = True
    with pytest.raises(_Cancelled):
        w._run_ffmpeg([sys.executable, "-c", "import time;time.sleep(30)"], duration_s=2.0)


def test_run_ffmpeg_parses_progress_from_stdout(q_app, tmp_path):
    w = _worker(tmp_path)
    seen = []
    w.signals.progress.connect(lambda a, b: seen.append(a))
    script = (
        "import sys\n"
        "print('out_time_us=500000', flush=True)\n"
        "print('out_time_us=1000000', flush=True)\n"
        "print('progress=end', flush=True)\n"
    )
    w._run_ffmpeg([sys.executable, "-c", script], duration_s=2.0)
    assert 25 in seen and 50 in seen


def test_parse_ffmpeg_progress_line():
    assert parse_ffmpeg_progress_line("out_time_us=500000", 2.0) == 25
    assert parse_ffmpeg_progress_line("out_time_us=N/A", 2.0) is None
    assert parse_ffmpeg_progress_line("frame=12", 2.0) is None
    assert parse_ffmpeg_progress_line("out_time_us=999999999", 1.0) == 99


def test_ffmpeg_thread_count_caps_auto_and_explicit():
    cpus = os.cpu_count() or 2
    auto = _ffmpeg_thread_count(0)
    assert 1 <= auto <= min(4, cpus)
    assert _ffmpeg_thread_count(999) == cpus
    assert _ffmpeg_thread_count(1) == 1


def test_ffmpeg_branch_passes_progress_threads_and_quiet(q_app, tmp_path, monkeypatch):
    w = _worker(tmp_path, encoder_threads=0)
    calls = []
    monkeypatch.setattr(w, "_run_ffmpeg", lambda cmd, duration_s=0.0: calls.append(cmd))
    w.signals.finished.connect(lambda *_: None)
    w.signals.error.connect(lambda m: pytest.fail(m))
    w.run()
    assert calls
    cmd = calls[0]
    assert "-progress" in cmd and cmd[cmd.index("-progress") + 1] == "pipe:1"
    assert "-loglevel" in cmd and "error" in cmd
    assert "-nostats" in cmd
    assert "-threads" in cmd
    threads = int(cmd[cmd.index("-threads") + 1])
    assert 1 <= threads <= min(4, os.cpu_count() or 2)
    assert "stderr=PIPE" not in str(cmd)
