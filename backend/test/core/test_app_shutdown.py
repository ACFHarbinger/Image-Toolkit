"""Robust SIGTERM/SIGINT shutdown: reap children, hard-exit watchdog, idempotent.

Regression for the zombie-after-kill state (icons stay, terminal unusable).
"""

from __future__ import annotations

import contextlib
import json
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


def test_persistent_slideshow_daemon_pids_require_active_config(tmp_path, monkeypatch):
    system_config = tmp_path / "slideshow.json"
    system_pid = tmp_path / "slideshow.pid"
    monitor_config = tmp_path / "monitor-slideshow.json"
    system_config.write_text(json.dumps({"running": True}), encoding="utf-8")
    system_pid.write_text("101", encoding="utf-8")
    monitor_config.write_text(json.dumps({"running": True, "pid": 202}), encoding="utf-8")
    monkeypatch.setattr(app_mod, "DAEMON_CONFIG_PATH", system_config)
    monkeypatch.setattr(app_mod, "PID_PATH", system_pid)
    monkeypatch.setattr(app_mod, "MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH", monitor_config)

    assert app_mod._persistent_slideshow_daemon_pids() == {101, 202}

    monitor_config.write_text(json.dumps({"running": False, "pid": 202}), encoding="utf-8")
    assert app_mod._persistent_slideshow_daemon_pids() == {101}


def test_reaper_preserves_persistent_daemon_process_tree(monkeypatch):
    class Process:
        def __init__(self, pid, parent=None):
            self.pid = pid
            self._parent = parent
            self.terminated = False
            self.killed = False

        def parent(self):
            return self._parent

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

    daemon = Process(101)
    daemon_child = Process(102, daemon)
    worker = Process(201)

    class Psutil:
        class Root:
            def children(self, recursive):
                assert recursive is True
                return [daemon, daemon_child, worker]

        @staticmethod
        def Process():
            return Psutil.Root()

        @staticmethod
        def wait_procs(processes, timeout):
            assert timeout == 2
            return [], list(processes)

    monkeypatch.setitem(sys.modules, "psutil", Psutil)
    monkeypatch.setattr(app_mod, "_persistent_slideshow_daemon_pids", lambda: {daemon.pid})

    app_mod._reap_child_processes()

    assert not daemon.terminated and not daemon.killed
    assert not daemon_child.terminated and not daemon_child.killed
    assert worker.terminated and worker.killed


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
