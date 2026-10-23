"""The shell is the request_focus caller Grok flagged on #877."""

from __future__ import annotations

from middleware.src.supervisor.gui_gate import GuiInstance
from middleware.src.supervisor.gui_shell import claim_or_focus, main


def test_claim_or_focus_requests_the_existing_owner(tmp_path) -> None:
    focused: list[str] = []
    first = claim_or_focus(tmp_path, on_focus=lambda: focused.append("ok"))
    assert first is not None
    try:
        assert claim_or_focus(tmp_path) is None
        assert focused == ["ok"]
    finally:
        first.release()


def test_cli_focuses_the_running_instance(tmp_path, capsys) -> None:
    holder = GuiInstance(tmp_path)
    focused: list[str] = []
    assert holder.acquire(on_focus=lambda: focused.append("ok")) is True
    try:
        assert main(["--data-dir", str(tmp_path)]) == 0
        assert FOCUSED_MARKER in capsys.readouterr().out
        assert focused == ["ok"]
    finally:
        holder.release()


FOCUSED_MARKER = "FOCUSED_OTHER"


def test_malformed_focus_request_does_not_kill_listener(tmp_path):
    import socket
    import time

    focused = []
    first = claim_or_focus(tmp_path, on_focus=lambda: focused.append(True))
    assert first is not None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(first.socket_path))
            client.sendall(b"[]\n")
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if first.request_focus():
                break
        assert focused
    finally:
        first.release()


def test_focus_request_is_dispatched_on_the_gui_poll_thread():
    import ast
    import threading
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "src/app.py"
    tree = ast.parse(source.read_text())
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in {"_on_gui_focus", "_drain_gui_focus_request"}
    ]
    called = []
    namespace = {
        "_gui_focus_requested": threading.Event(),
        "_raise_main_window": lambda: called.append(threading.get_ident()),
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)
    worker = threading.Thread(target=namespace["_on_gui_focus"])
    worker.start()
    worker.join()
    assert not called
    namespace["_drain_gui_focus_request"]()
    assert called == [threading.get_ident()]


def test_failed_claim_cannot_unlink_owners_focus_socket(tmp_path):
    holder = GuiInstance(tmp_path)
    other = GuiInstance(tmp_path)
    assert holder.acquire()
    try:
        assert not other.acquire()
        other.release()
        assert holder.socket_path.exists()
    finally:
        holder.release()


def test_failed_socket_setup_releases_gui_lock(tmp_path):
    import pytest

    from middleware.src.supervisor.lock import DataDirLock

    path = tmp_path / ("x" * 110)
    gate = GuiInstance(path)
    with pytest.raises(OSError):
        gate.acquire()
    lock = DataDirLock(path, "gui")
    assert lock.acquire()
    lock.release()
