"""Regression tests: slideshow daemons must pause during screen lock.

Bug: when the PC goes to the lock screen the slideshow appeared to stop.
Root causes:
  1. slideshow_daemon.py — elapsed kept accumulating while locked, so
     wallpapers were "skipped" during lock time and the daemon waited another
     full interval after unlock before showing the next image.
  2. monitor_slideshow_daemon.py — the apply callback fired from the native
     C++ scheduler while locked; on KDE it errored, on GNOME it silently
     had no visible effect. Either way the queue advanced with no result.

Fix:
  1. slideshow_daemon.py   — `_is_session_locked()` pauses elapsed and defers
     the first apply-after-unlock via the `_was_locked` flag.
  2. monitor_slideshow_daemon.py — the apply callback stores the path in a
     `pending` dict while locked; the polling loop flushes it on unlock.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# _is_session_locked()
# ---------------------------------------------------------------------------

class TestIsSessionLocked:
    def test_returns_false_when_loginctl_says_no(self):
        from backend.src.utils.display.slideshow_daemon import _is_session_locked

        with patch(
            "backend.src.utils.display.slideshow_daemon._SESSION_ID", "3"
        ), patch(
            "backend.src.utils.display.slideshow_daemon.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(stdout="no\n")
            assert _is_session_locked() is False

    def test_returns_true_when_loginctl_says_yes(self):
        from backend.src.utils.display.slideshow_daemon import _is_session_locked

        with patch(
            "backend.src.utils.display.slideshow_daemon._SESSION_ID", "3"
        ), patch(
            "backend.src.utils.display.slideshow_daemon.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(stdout="yes\n")
            assert _is_session_locked() is True

    def test_returns_false_when_no_session_id(self):
        from backend.src.utils.display.slideshow_daemon import _is_session_locked

        with patch("backend.src.utils.display.slideshow_daemon._SESSION_ID", ""):
            # Should not call subprocess at all when SESSION_ID is empty.
            with patch(
                "backend.src.utils.display.slideshow_daemon.subprocess.run"
            ) as mock_run:
                assert _is_session_locked() is False
                mock_run.assert_not_called()

    def test_returns_false_when_loginctl_errors(self):
        from backend.src.utils.display.slideshow_daemon import _is_session_locked

        with patch(
            "backend.src.utils.display.slideshow_daemon._SESSION_ID", "3"
        ), patch(
            "backend.src.utils.display.slideshow_daemon.subprocess.run",
            side_effect=FileNotFoundError("loginctl not found"),
        ):
            # Should not raise; fall back to False (assume unlocked).
            assert _is_session_locked() is False


# ---------------------------------------------------------------------------
# apply_runtime_config — locked state must not affect stop decision
# ---------------------------------------------------------------------------

class TestApplyRuntimeConfigUnchanged:
    def test_stop_decision_unchanged_by_lock(self):
        """The stop decision is driven by config['running'], not lock state."""
        from backend.src.utils.display.slideshow_daemon import apply_runtime_config

        cfg = {"running": True, "interval_seconds": 30, "style": "zoom", "use_video_runtime_interval": False}
        result = apply_runtime_config(cfg, interval=30, style="zoom", use_video_runtime=False)
        assert result["stop"] is False

        cfg["running"] = False
        result = apply_runtime_config(cfg, interval=30, style="zoom", use_video_runtime=False)
        assert result["stop"] is True


# ---------------------------------------------------------------------------
# make_apply_callback — deferred apply while locked
# ---------------------------------------------------------------------------

class TestMakeApplyCallbackLockDeferred:
    def _make_cb(self, locked: bool):
        """Build a callback with _is_session_locked patched to ``locked``."""
        from backend.src.utils.display.monitor_slideshow_daemon import make_apply_callback
        from unittest.mock import MagicMock

        monitors = []
        with patch(
            "backend.src.utils.display.monitor_slideshow_daemon._is_session_locked",
            return_value=locked,
        ), patch(
            "backend.src.utils.display.monitor_slideshow_daemon.WallpaperManager"
        ) as mock_wm:
            cb = make_apply_callback(monitors, style="Fill", video_style="Scaled and Cropped")
            return cb, mock_wm

    def test_wallpaper_applied_when_unlocked(self):
        from backend.src.utils.display.monitor_slideshow_daemon import make_apply_callback

        with patch(
            "backend.src.utils.display.monitor_slideshow_daemon._is_session_locked",
            return_value=False,
        ), patch(
            "backend.src.utils.display.monitor_slideshow_daemon.WallpaperManager"
        ) as mock_wm:
            cb = make_apply_callback([], style="Fill", video_style="Scaled and Cropped")
            cb("0", "/img/a.jpg", 0)
            mock_wm.apply_wallpaper.assert_called_once()


    def test_wallpaper_deferred_when_locked(self):
        from backend.src.utils.display.monitor_slideshow_daemon import make_apply_callback

        with patch(
            "backend.src.utils.display.monitor_slideshow_daemon._is_session_locked",
            return_value=True,
        ), patch(
            "backend.src.utils.display.monitor_slideshow_daemon.WallpaperManager"
        ) as mock_wm:
            cb = make_apply_callback([], style="Fill", video_style="Scaled and Cropped")
            cb("0", "/img/a.jpg", 0)

        # Wallpaper must NOT have been applied while locked.
        mock_wm.apply_wallpaper.assert_not_called()
        # Path must be stored for deferred apply on unlock.
        assert cb.pending.get("0") == "/img/a.jpg"

    def test_pending_cleared_and_applied_on_unlock(self):
        """Simulates: locked → wallpaper skipped into pending → unlocked →
        pending flushed by applying immediately."""
        from backend.src.utils.display.monitor_slideshow_daemon import make_apply_callback

        apply_calls = []

        with patch(
            "backend.src.utils.display.monitor_slideshow_daemon._is_session_locked",
            return_value=True,
        ), patch(
            "backend.src.utils.display.monitor_slideshow_daemon.WallpaperManager"
        ):
            cb = make_apply_callback([], style="Fill", video_style="Scaled and Cropped")
            cb("0", "/img/b.jpg", 1)  # locked → goes into pending

        assert cb.pending.get("0") == "/img/b.jpg"

        # Simulate unlock: polling loop flushes pending by calling apply_cb directly.
        with patch(
            "backend.src.utils.display.monitor_slideshow_daemon._is_session_locked",
            return_value=False,
        ), patch(
            "backend.src.utils.display.monitor_slideshow_daemon.WallpaperManager"
        ) as mock_wm:
            pending = cb.pending
            for mid, path in list(pending.items()):
                cb(mid, path, -1)
                pending.pop(mid, None)

        mock_wm.apply_wallpaper.assert_called_once()
        assert cb.pending == {}

    def test_multiple_advances_while_locked_stores_latest(self):
        """If the native scheduler fires several times while locked, only the
        most recent path should be shown on unlock (not a replay of all missed
        images — that would be confusing)."""
        from backend.src.utils.display.monitor_slideshow_daemon import make_apply_callback

        with patch(
            "backend.src.utils.display.monitor_slideshow_daemon._is_session_locked",
            return_value=True,
        ), patch(
            "backend.src.utils.display.monitor_slideshow_daemon.WallpaperManager"
        ):
            cb = make_apply_callback([], style="Fill", video_style="Scaled and Cropped")
            cb("0", "/img/first.jpg", 0)
            cb("0", "/img/second.jpg", 1)
            cb("0", "/img/third.jpg", 2)

        # Only the latest path is stored (dict key "0" overwritten each call).
        assert cb.pending.get("0") == "/img/third.jpg"
