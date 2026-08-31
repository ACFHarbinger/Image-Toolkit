"""GIF extractor worker: two-pass palette + non-deadlocking ffmpeg run."""

from __future__ import annotations

import sys

import pytest

from gui.src.helpers.video.gif_extractor_worker import GifCreationWorker, _Cancelled

pytestmark = pytest.mark.gui


def _worker(tmp_path, **kw):
    return GifCreationWorker(
        video_path=str(tmp_path / "v.mp4"),
        start_ms=0,
        end_ms=2000,
        output_path=str(tmp_path / "out.gif"),
        use_ffmpeg=True,
        fps=15,
        **kw,
    )


def test_run_ffmpeg_does_not_deadlock_on_large_stderr(q_app, tmp_path):
    """A child that floods stderr well past the 64 KB pipe buffer must not hang."""
    w = _worker(tmp_path)
    flood = (
        "import sys; sys.stderr.write('x' * 500_000); sys.stderr.flush()"
    )
    # returncode 0 -> no RuntimeError
    w._run_ffmpeg([sys.executable, "-c", flood], "flood")


def test_run_ffmpeg_reports_failure_with_stderr_tail(q_app, tmp_path):
    w = _worker(tmp_path)
    with pytest.raises(RuntimeError) as ei:
        w._run_ffmpeg(
            [sys.executable, "-c", "import sys;sys.stderr.write('boom');sys.exit(2)"],
            "encode",
        )
    assert "boom" in str(ei.value) and "code 2" in str(ei.value)


def test_run_ffmpeg_cancel_raises(q_app, tmp_path):
    w = _worker(tmp_path)
    w._is_cancelled = True
    with pytest.raises(_Cancelled):
        w._run_ffmpeg([sys.executable, "-c", "import time;time.sleep(30)"], "encode")


def test_ffmpeg_branch_is_two_pass_palette(q_app, tmp_path, monkeypatch):
    w = _worker(tmp_path, target_size=(320, 240))
    calls = []
    monkeypatch.setattr(w, "_run_ffmpeg", lambda cmd, phase: calls.append((phase, cmd)))
    w.signals.finished.connect(lambda *_: None)
    w.signals.error.connect(lambda m: pytest.fail(m))
    w.run()

    assert [c[0] for c in calls] == ["palette", "encode"]
    pass1 = " ".join(calls[0][1])
    pass2 = " ".join(calls[1][1])
    assert "palettegen=max_colors=256" in pass1
    assert "paletteuse" in pass2 and "palettegen" not in pass2
    # no single-pass split buffer
    assert "split[s0][s1]" not in pass1 and "split[s0][s1]" not in pass2
    assert "-loglevel error" in pass1  # quiet + stderr-to-file safe
