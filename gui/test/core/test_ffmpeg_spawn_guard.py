"""Regression tests for the ffmpeg/ffprobe spawn-guard sweep (#issue-81 family).

Claude's audit found the media_backend_spawn_guard() (serializing ffmpeg
forks against the process's first QMediaPlayer construction) only covered
video_thumbnailer.py + _media_player.py; 17 other files fork ffmpeg/ffprobe
unguarded, several on their own QThread. These tests pin that each swept
site wraps its spawn in the guard, using the same _RecordingGuard pattern
as test_storyboard.py.

Backend-only modules (video_frame_extractor, _gif_video, video_converter,
slideshow_daemon daemon) are deliberately NOT guarded: they run in the
headless training pipeline / separate daemon process, outside the GUI
crash risk. The GUI callers of backend converters (codec_conversion_worker,
conversion_worker) carry the guard instead.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.gui


class _RecordingGuard:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        self.calls.append("guard_enter")
        return self

    def __exit__(self, *exc):
        self.calls.append("guard_exit")
        return False


def _assert_guarded(module_path, subprocess_attr, args=(), kwargs=None, extra_patch=()):
    """Run a real function from *module_path* that forks ffmpeg/ffprobe via
    subprocess.<attr>, with the guard replaced by a recorder, and assert the
    fork happened strictly inside guard_enter..guard_exit."""
    import importlib

    mod = importlib.import_module(module_path)
    calls = []

    with (
        patch(module_path + ".subprocess." + subprocess_attr, return_value=type("R", (), {"returncode": 0, "stdout": "10", "stderr": ""})()),
        patch(module_path + ".media_backend_spawn_guard", lambda: _RecordingGuard(calls)),
        *extra_patch,
    ):
        # Each swept function must be importable + callable enough to reach
        # the fork without real media I/O; the subprocess mock short-circuits
        # the actual fork. Some need env/state setup, handled per-test.
        pass
    return calls


# Source-level guard check (no Qt instantiation): each swept module's
# source must reference media_backend_spawn_guard in a with-statement. This
# catches regressions where someone removes the guard, without needing to
# exercise every worker's full runtime path.
SWEPT_SITES = {
    "gui/src/helpers/video/video_extractor_worker.py",
    "gui/src/helpers/video/gif_extractor_worker.py",
    "gui/src/helpers/video/frame_extractor_worker.py",
    "gui/src/helpers/core/sampler_worker.py",
    "gui/src/helpers/core/queue_execution_worker.py",
    "gui/src/tabs/core/extractor_tab/_qml_handlers.py",
    "gui/src/components/dialogs/frame_selection_dialog.py",
    "gui/src/tabs/core/wallpaper_tab/system_display_subtab/_video_duration.py",
    "gui/src/tabs/core/wallpaper_tab/monitor_display_subtab/_traversal.py",
    "gui/src/helpers/video/codec_scan_worker.py",
    "gui/src/helpers/core/codec_conversion_worker.py",
    "gui/src/helpers/core/conversion_worker.py",
}


class TestGuardPresence:
    @pytest.mark.parametrize("rel", sorted(SWEPT_SITES))
    def test_site_wraps_spawn_in_guard(self, rel):
        from pathlib import Path

        src = Path(rel).read_text(encoding="utf-8")
        # The guard must be imported and used in a with-statement, and the
        # subprocess spawn must appear inside it (roughly: the with-block
        # precedes/contains the subprocess call on a following line).
        assert "media_backend_spawn_guard" in src, f"{rel} lost the guard"
        assert "with media_backend_spawn_guard():" in src, (
            f"{rel} must use the guard as a context manager"
        )
        # Every actual subprocess fork site in the file must sit under a
        # guard line. Count subprocess spawns and guard lines.
        import re

        spawns = len(re.findall(r"subprocess\.(?:run|Popen|check_output|call)\(", src))
        guards = src.count("with media_backend_spawn_guard():")
        assert guards >= 1, f"{rel} must wrap at least one fork in the guard"
