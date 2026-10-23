"""Single-instance gate for GUI apps on the data directory (Kimi Q2)."""

from __future__ import annotations

import contextlib
import json
import os
import socket
import threading
from collections.abc import Callable
from pathlib import Path

from middleware.src.supervisor.lock import DataDirLock

FOCUS_OP = "focus"


class GuiInstance:
    """Exclusive GUI lock plus a local focus socket."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._lock = DataDirLock(data_dir, "gui")
        self._sock_path = data_dir / "gui.focus.sock"
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._owns_lock = False
        self._on_focus: Callable[[], None] | None = None

    @property
    def socket_path(self) -> Path:
        return self._sock_path

    def acquire(self, on_focus: Callable[[], None] | None = None) -> bool:
        if not self._lock.acquire():
            return False
        self._owns_lock = True
        self._on_focus = on_focus
        try:
            self._serve()
        except BaseException:
            self._lock.release()
            self._owns_lock = False
            raise
        return True

    def release(self) -> None:
        if not self._owns_lock:
            return
        self._stop.set()
        if self._server is not None:
            with contextlib.suppress(OSError):
                self._server.shutdown(socket.SHUT_RDWR)
            self._server.close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._sock_path.exists():
            self._sock_path.unlink()
        self._lock.release()
        self._owns_lock = False

    def request_focus(self, timeout_s: float = 1.0) -> bool:
        if not self._sock_path.exists():
            return False
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout_s)
        try:
            sock.connect(str(self._sock_path))
            sock.sendall(json.dumps({"op": FOCUS_OP}).encode("utf-8") + b"\n")
            reply = sock.recv(64)
        except OSError:
            return False
        finally:
            sock.close()
        return b"ok" in reply

    def _serve(self) -> None:
        if self._sock_path.exists():
            self._sock_path.unlink()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self._sock_path))
        os.chmod(self._sock_path, 0o600)
        server.listen(4)
        self._server = server
        self._stop.clear()
        self._thread = threading.Thread(target=self._accept, name="itk-gui-focus", daemon=True)
        self._thread.start()

    def _accept(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                conn, _addr = self._server.accept()
            except OSError:
                return
            with conn:
                try:
                    conn.settimeout(1.0)
                    raw = conn.recv(256)
                    payload = json.loads(raw.decode("utf-8").splitlines()[0])
                    if not isinstance(payload, dict):
                        continue
                    if payload.get("op") == FOCUS_OP and self._on_focus is not None:
                        self._on_focus()
                    conn.sendall(b"ok\n")
                except (OSError, UnicodeDecodeError, json.JSONDecodeError, IndexError):
                    continue
