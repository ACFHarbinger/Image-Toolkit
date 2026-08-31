"""Robust SIGTERM/SIGINT shutdown: reap children, hard-exit watchdog, idempotent.

Regression for the zombie-after-kill state (icons stay, terminal unusable).
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
import time

import psutil

from backend.src import app as app_mod


def test_reap_child_processes_kills_descendants():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    grand = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import subprocess,sys,time;"
            "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
            "time.sleep(60)",
        ]
    )
    try:
        assert psutil.pid_exists(child.pid)
        app_mod._reap_child_processes()
        for _ in range(30):
            if not psutil.pid_exists(child.pid) and not psutil.pid_exists(grand.pid):
                break
            time.sleep(0.1)
        assert not psutil.pid_exists(child.pid)
        assert not psutil.pid_exists(grand.pid)
    finally:
        for p in (child, grand):
            with contextlib.suppress(Exception):
                p.kill()


def test_second_signal_forces_hard_exit(monkeypatch):
    calls = {"exit": 0, "reap": 0, "quit": 0}
    monkeypatch.setattr(
        app_mod.os, "_exit", lambda code=0: calls.__setitem__("exit", code or 1)
    )
    monkeypatch.setattr(
        app_mod, "_reap_child_processes",
        lambda: calls.__setitem__("reap", calls["reap"] + 1),
    )

    class _App:
        class _Sig:
            def connect(self, *_):
                pass

        aboutToQuit = _Sig()

        def quit(self):
            calls["quit"] += 1

    handlers = {}
    monkeypatch.setattr(
        app_mod.signal, "signal", lambda s, h: handlers.__setitem__(s, h)
    )

    class _FakeTimer:
        def __init__(self, *a, **k):
            self.daemon = True

        def start(self):
            pass

    monkeypatch.setattr(app_mod.threading, "Timer", _FakeTimer)

    app_mod._install_shutdown_handlers(_App(), lambda: None)
    h = handlers[app_mod.signal.SIGTERM]

    h(app_mod.signal.SIGTERM, None)  # 1st: graceful path, no os._exit
    assert calls["quit"] == 1 and calls["exit"] == 0
    h(app_mod.signal.SIGTERM, None)  # 2nd: hard exit
    assert calls["exit"] == 1 and calls["reap"] >= 1
