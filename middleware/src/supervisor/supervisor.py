"""Sibling-process supervisor (Grok T5, Mistral M6)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

from middleware.src.supervisor.children import (
    CHILD_NAMES,
    SIDECAR,
    ChildHandle,
    child_running,
    heartbeat,
    reattach,
    spawn,
    terminate,
)
from middleware.src.supervisor.envelope import (
    BRIDGE_DOWN,
    BRIDGE_READY,
    PROTOCOL_VERSION,
    BridgeEvent,
    ErrorEnvelope,
    bridge_unavailable,
)
from middleware.src.supervisor.lock import DataDirLock

Listener = Callable[[BridgeEvent], None]


class Supervisor:
    """Start sidecar, cloud_jobs and slideshow as siblings; restart the sidecar."""

    def __init__(
        self,
        data_dir: Path,
        *,
        poll_interval_s: float = 0.2,
        spawn_child: Callable[[str, Path], ChildHandle] | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.poll_interval_s = poll_interval_s
        self._spawn_child = spawn_child or (lambda name, path: spawn(name, path))
        self._lock = DataDirLock(data_dir, "supervisor")
        self._children: dict[str, ChildHandle] = {}
        self._events: list[BridgeEvent] = []
        self._listeners: list[Listener] = []
        self._inflight: dict[str, threading.Event] = {}
        self._inflight_errors: dict[str, ErrorEnvelope] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._mu = threading.Lock()

    @property
    def children(self) -> dict[str, ChildHandle]:
        with self._mu:
            return dict(self._children)

    def events(self) -> tuple[BridgeEvent, ...]:
        with self._mu:
            return tuple(self._events)

    def add_listener(self, listener: Listener) -> None:
        with self._mu:
            self._listeners.append(listener)

    def start(self) -> None:
        if not self._lock.acquire():
            raise RuntimeError(f"supervisor already running for {self.data_dir}")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._stop.clear()
        for name in CHILD_NAMES:
            handle = reattach(name, self.data_dir)
            if handle is None:
                handle = self._spawn_child(name, self.data_dir)
            with self._mu:
                self._children[name] = handle
        self._thread = threading.Thread(
            target=self._run, name="itk-supervisor", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        with self._mu:
            handles = list(self._children.values())
            self._children.clear()
        for handle in handles:
            terminate(handle)
        self._lock.release()

    def wait_until_ready(self, timeout_s: float = 5.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if all(self._child_ready(name) for name in CHILD_NAMES):
                return
            time.sleep(0.02)
        missing = [name for name in CHILD_NAMES if not self._child_ready(name)]
        raise TimeoutError(f"children not ready: {missing}")

    def begin_session(self, request_id: str) -> ErrorEnvelope | None:
        """Register an in-flight session request. Returns an error if the sidecar is down."""
        sidecar = self.children.get(SIDECAR)
        if sidecar is None or not child_running(sidecar):
            return bridge_unavailable(sidecar_pid=None)
        done = threading.Event()
        with self._mu:
            self._inflight[request_id] = done
        return None

    def session_error(self, request_id: str) -> ErrorEnvelope | None:
        with self._mu:
            return self._inflight_errors.get(request_id)

    def finish_session(self, request_id: str) -> None:
        with self._mu:
            self._inflight.pop(request_id, None)
            self._inflight_errors.pop(request_id, None)

    def _child_ready(self, name: str) -> bool:
        handle = self.children.get(name)
        if handle is None or not child_running(handle):
            return False
        beat = heartbeat(self.data_dir, name)
        return bool(beat) and int(beat.get("pid", -1)) == handle.pid

    def _run(self) -> None:
        while not self._stop.is_set():
            self._tick()
            self._stop.wait(self.poll_interval_s)

    def _tick(self) -> None:
        sidecar = self.children.get(SIDECAR)
        if sidecar is not None and not child_running(sidecar):
            self._on_sidecar_down(sidecar.pid)
            if not self._stop.is_set():
                replacement = self._spawn_child(SIDECAR, self.data_dir)
                with self._mu:
                    self._children[SIDECAR] = replacement
                self._emit(
                    BridgeEvent(
                        name=BRIDGE_READY,
                        protocol_version=PROTOCOL_VERSION,
                        sidecar_pid=replacement.pid,
                        previous_sidecar_pid=sidecar.pid,
                    )
                )
        for name in CHILD_NAMES:
            if name == SIDECAR:
                continue
            child = self.children.get(name)
            if child is not None and not child_running(child) and not self._stop.is_set():
                replacement = self._spawn_child(name, self.data_dir)
                with self._mu:
                    self._children[name] = replacement

    def _on_sidecar_down(self, pid: int) -> None:
        error = bridge_unavailable(sidecar_pid=pid)
        with self._mu:
            for request_id, event in self._inflight.items():
                self._inflight_errors[request_id] = error
                event.set()
            self._inflight.clear()
        self._emit(
            BridgeEvent(name=BRIDGE_DOWN, sidecar_pid=pid, protocol_version=None)
        )

    def _emit(self, event: BridgeEvent) -> None:
        with self._mu:
            self._events.append(event)
            listeners = list(self._listeners)
        for listener in listeners:
            listener(event)
