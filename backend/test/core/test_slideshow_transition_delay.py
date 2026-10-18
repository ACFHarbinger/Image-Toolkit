"""Transition delay: every slideshow interval is extended by a few seconds."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from backend.src.constants import DEFAULT_TRANSITION_DELAY_SECONDS
from backend.src.utils.display import monitor_slideshow_daemon, slideshow_daemon


@pytest.mark.parametrize(
    ("cfg", "expected"),
    [
        ({}, DEFAULT_TRANSITION_DELAY_SECONDS),
        ({"transition_delay_seconds": 7}, 7),
        ({"transition_delay_seconds": 0}, 0),
        ({"transition_delay_seconds": -4}, 0),
        ({"transition_delay_seconds": 999}, 60),
        ({"transition_delay_seconds": "x"}, DEFAULT_TRANSITION_DELAY_SECONDS),
    ],
)
def test_transition_delay_parsing(cfg, expected):
    assert slideshow_daemon.transition_delay_seconds(cfg) == expected


def _run_daemon(tmp_path, monkeypatch, cfg, ticks):
    config_path = tmp_path / "daemon.json"
    config_path.write_text(json.dumps(cfg))
    clock = {"tick": 0}
    applied_at = []

    def fake_sleep(_s):
        clock["tick"] += 1
        if clock["tick"] > ticks:
            raise KeyboardInterrupt

    def fake_apply(*_a, **_kw):
        applied_at.append(clock["tick"])

    monkeypatch.setattr(slideshow_daemon, "DAEMON_CONFIG_PATH", config_path)
    monkeypatch.setattr(slideshow_daemon, "PID_PATH", tmp_path / "daemon.pid")
    monkeypatch.setattr(slideshow_daemon, "_apply_all", fake_apply)
    monkeypatch.setattr(slideshow_daemon, "_is_session_locked", lambda: False)
    monkeypatch.setattr(
        slideshow_daemon, "time", type("T", (), {"sleep": staticmethod(fake_sleep), "time": staticmethod(lambda: 1000.0)})
    )
    slideshow_daemon.run()
    return applied_at, json.loads(config_path.read_text())


def _cfg(**extra):
    return {
        "running": True,
        "interval_seconds": 30,
        "playback_order": "Sequential",
        "style": "Fill",
        "monitor_queues": {"0": ["/a.png", "/b.png"]},
        "current_paths": {"0": "/a.png"},
        "monitor_geometries": {"0": {"x": 0, "y": 0, "width": 1920, "height": 1080}},
        **extra,
    }


def test_daemon_advances_after_interval_plus_delay(tmp_path, monkeypatch):
    applied_at, final = _run_daemon(tmp_path, monkeypatch, _cfg(transition_delay_seconds=3), ticks=70)
    # First apply at start, then every 30 + 3 seconds.
    assert applied_at == [0, 33, 66]
    # The stored interval stays the user's value; the delay is never folded in.
    assert final["interval_seconds"] == 30


def test_daemon_default_delay_applies_to_old_configs(tmp_path, monkeypatch):
    applied_at, _ = _run_daemon(tmp_path, monkeypatch, _cfg(), ticks=40)
    assert applied_at == [0, 30 + DEFAULT_TRANSITION_DELAY_SECONDS]


def test_daemon_zero_delay_keeps_exact_interval(tmp_path, monkeypatch):
    applied_at, _ = _run_daemon(tmp_path, monkeypatch, _cfg(transition_delay_seconds=0), ticks=61)
    assert applied_at == [0, 30, 60]


def test_monitor_scheduler_durations_include_delay():
    with patch.object(monitor_slideshow_daemon, "base") as base:
        base.run_monitor_slideshow.return_value = "{}"
        monitor_slideshow_daemon.start(
            "0", ["/a.png", "/b.png"], [90, 20], monitors=[], callback=lambda *a: None, transition_delay=3
        )
        sent = json.loads(base.run_monitor_slideshow.call_args[0][1])
    assert sent["durations"] == [93, 23]
