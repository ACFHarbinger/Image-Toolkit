"""Start-time queue lock for the system-display slideshow daemon."""

from __future__ import annotations

from backend.src.utils.display.slideshow_daemon import apply_runtime_config


class TestApplyRuntimeConfig:
    def test_empty_or_stopped_means_stop(self):
        assert apply_runtime_config({}, interval=30, style="Fill", use_video_runtime=False)[
            "stop"
        ]
        assert apply_runtime_config(
            {"running": False, "monitor_queues": {}},
            interval=30,
            style="Fill",
            use_video_runtime=False,
        )["stop"]

    def test_running_with_empty_queues_does_not_stop(self):
        decision = apply_runtime_config(
            {
                "running": True,
                "monitor_queues": {},
                "interval_seconds": 30,
                "style": "Fill",
            },
            interval=30,
            style="Fill",
            use_video_runtime=False,
        )
        assert decision["stop"] is False
        assert decision["interval"] == 30

    def test_interval_change_resets_elapsed(self):
        decision = apply_runtime_config(
            {"running": True, "interval_seconds": 90, "style": "Fill"},
            interval=30,
            style="Fill",
            use_video_runtime=False,
        )
        assert decision["reset_elapsed"] is True
        assert decision["interval"] == 90

    def test_does_not_expose_queues(self):
        decision = apply_runtime_config(
            {"running": True, "monitor_queues": {"0": ["/new.jpg"]}},
            interval=30,
            style="Fill",
            use_video_runtime=False,
        )
        assert "monitor_queues" not in decision
        assert decision["stop"] is False
