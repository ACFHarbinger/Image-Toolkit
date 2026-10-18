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


# --- Reset Timer --------------------------------------------------------------


def test_runtime_config_detects_reset_token_changes():
    base = {"running": True, "interval_seconds": 30}
    kw = {"interval": 30, "style": "Fill", "use_video_runtime": False}
    assert slideshow_daemon.apply_runtime_config(base, **kw)["timer_reset"] is False
    first = slideshow_daemon.apply_runtime_config({**base, "timer_reset_token": 5}, reset_token=None, **kw)
    assert first["timer_reset"] is True and first["reset_token"] == 5
    assert slideshow_daemon.apply_runtime_config({**base, "timer_reset_token": 5}, reset_token=5, **kw)["timer_reset"] is False
    # A GUI rewrite that drops the key is not a reset and keeps the last token.
    dropped = slideshow_daemon.apply_runtime_config(base, reset_token=5, **kw)
    assert dropped["timer_reset"] is False and dropped["reset_token"] == 5
    assert dropped["reset_elapsed"] is False


def test_daemon_reset_restarts_interval_without_advancing(tmp_path, monkeypatch):
    config_path = tmp_path / "daemon.json"

    def on_tick(tick):
        if tick == 20:  # the user presses Reset Timer 20 s into the interval
            cfg = json.loads(config_path.read_text())
            cfg["timer_reset_token"] = 123
            config_path.write_text(json.dumps(cfg))

    applied_at, final = _run_daemon_with_hook(tmp_path, monkeypatch, _cfg(transition_delay_seconds=3), 60, on_tick)
    # Without the reset the change would come at 33; the reset at 20 moves it to 53.
    assert applied_at == [0, 53]
    assert final["timer_reset_token"] == 123


def _run_daemon_with_hook(tmp_path, monkeypatch, cfg, ticks, hook):
    config_path = tmp_path / "daemon.json"
    config_path.write_text(json.dumps(cfg))
    clock = {"tick": 0}
    applied_at = []

    def fake_sleep(_s):
        clock["tick"] += 1
        if clock["tick"] > ticks:
            raise KeyboardInterrupt
        hook(clock["tick"])

    monkeypatch.setattr(slideshow_daemon, "DAEMON_CONFIG_PATH", config_path)
    monkeypatch.setattr(slideshow_daemon, "PID_PATH", tmp_path / "daemon.pid")
    monkeypatch.setattr(slideshow_daemon, "_apply_all", lambda *a, **k: applied_at.append(clock["tick"]))
    monkeypatch.setattr(slideshow_daemon, "_is_session_locked", lambda: False)
    monkeypatch.setattr(
        slideshow_daemon, "time", type("T", (), {"sleep": staticmethod(fake_sleep), "time": staticmethod(lambda: 1000.0)})
    )
    slideshow_daemon.run()
    return applied_at, json.loads(config_path.read_text())


def test_skip_first_call_wrapper():
    calls = []
    wrapped = monitor_slideshow_daemon.skip_first_call(lambda *a: calls.append(a))
    wrapped("0", "/a.png", 0)
    wrapped("0", "/b.png", 1)
    assert calls == [("0", "/b.png", 1)]


def test_monitor_daemon_restarts_scheduler_on_reset(monkeypatch):
    configs = [
        {"running": True, "monitor_id": "0", "queue": ["/a", "/b", "/c"], "durations": [10, 10, 10], "current_index": 0},
        {"running": True, "monitor_id": "0", "queue": ["/a", "/b", "/c"], "current_index": 2},
        {"running": True, "monitor_id": "0", "queue": ["/a", "/b", "/c"], "current_index": 2, "timer_reset_token": 9},
        {"running": True, "monitor_id": "0", "queue": ["/a", "/b", "/c"], "current_index": 2, "timer_reset_token": 9},
        {"running": False},
    ]
    feed = iter(configs + [{"running": False}] * 5)
    starts, stops = [], []
    m = monitor_slideshow_daemon
    monkeypatch.setattr(m, "_load_gui_config", lambda: dict(next(feed)))
    monkeypatch.setattr(m, "_write_gui_config", lambda cfg: None)
    monkeypatch.setattr(m, "mark_stopped", lambda cfg=None: None)
    monkeypatch.setattr(m, "_is_session_locked", lambda: False)
    monkeypatch.setattr(m, "make_apply_callback", lambda *a, **k: (lambda *x: None))
    monkeypatch.setattr(m, "start", lambda *a, **k: starts.append(k))
    monkeypatch.setattr(m, "stop", lambda: stops.append(1))
    monkeypatch.setattr(m, "status", lambda: {"current_index": 2})
    monkeypatch.setattr(m, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))
    m.run()
    assert [k["start_index"] for k in starts] == [0, 2]
    assert [k["skip_first_apply"] for k in starts] == [False, True]
    # One stop for the reset restart, one on exit.
    assert len(stops) == 2
