"""Sibling-process supervisor (Grok T5, Mistral M6)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

from middleware.src.supervisor.binding import (
    DAEMON_STORES,
    BindingError,
    DaemonMinter,
    ProductionHandoff,
    lease_still_valid,
    load_lease_meta,
    load_or_create_session,
    renew_before,
    save_lease_meta,
)
from middleware.src.supervisor.children import (
    CHILD_NAMES,
    SIDECAR,
    ChildHandle,
    child_running,
    heartbeat,
    pid_path,
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
        use_real_sidecar: bool = False,
        python_executable: str | None = None,
        vault: DaemonMinter | None = None,
        lease_ttl_seconds: int = 300,
    ) -> None:
        self.data_dir = data_dir
        self.poll_interval_s = poll_interval_s
        self._handoff = ProductionHandoff(vault) if vault is not None else None
        self._lease_ttl = lease_ttl_seconds
        self._session_id: str | None = None
        self._spawn_child = spawn_child or (
            lambda name, path: spawn(
                name,
                path,
                use_real_sidecar=use_real_sidecar,
                python_executable=python_executable,
            )
        )
        self._lock = DataDirLock(data_dir, "supervisor")
        self._children: dict[str, ChildHandle] = {}
        self._events: list[BridgeEvent] = []
        self._listeners: list[Listener] = []
        self._inflight: dict[str, threading.Event] = {}
        self._inflight_errors: dict[str, ErrorEnvelope] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._mu = threading.Lock()
        self._pending_ready: tuple[int, int] | None = None

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
        try:
            if self._handoff is not None:
                self._session_id, session_existed = load_or_create_session(self.data_dir)
            else:
                session_existed = False
            for name in CHILD_NAMES:
                handle = self._adopt_or_spawn(name, session_existed)
                with self._mu:
                    self._children[name] = handle
        except Exception:
            self._fail_start()
            raise
        self._thread = threading.Thread(target=self._run, name="itk-supervisor", daemon=True)
        self._thread.start()

    def stop(self, *, reap_children: bool = True) -> None:
        """Stop the supervisor.

        ``reap_children=False`` is the process-restart path: durable
        siblings and the sidecar stay up so the next supervisor reattaches.
        A window close must not be what calls this with reaping enabled.
        """
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        with self._mu:
            handles = list(self._children.values())
            self._children.clear()
            self._pending_ready = None
        if reap_children:
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
                replacement = self._launch(SIDECAR)
                with self._mu:
                    self._children[SIDECAR] = replacement
                    self._pending_ready = (replacement.pid, sidecar.pid)
        elif self._pending_ready is not None and self._child_ready(SIDECAR):
            ready_pid, previous_pid = self._pending_ready
            current = self.children.get(SIDECAR)
            if current is not None and current.pid == ready_pid:
                self._pending_ready = None
                self._emit(
                    BridgeEvent(
                        name=BRIDGE_READY,
                        protocol_version=PROTOCOL_VERSION,
                        sidecar_pid=ready_pid,
                        previous_sidecar_pid=previous_pid,
                    )
                )
        for name in CHILD_NAMES:
            if name == SIDECAR:
                continue
            child = self.children.get(name)
            if child is None or self._stop.is_set():
                continue
            if not child_running(child):
                try:
                    replacement = self._launch(name)
                except Exception:
                    continue
                with self._mu:
                    self._children[name] = replacement
            elif self._handoff is not None:
                self._maintain_lease(name, child)

    def _on_sidecar_down(self, pid: int) -> None:
        error = bridge_unavailable(sidecar_pid=pid)
        with self._mu:
            for request_id, event in self._inflight.items():
                self._inflight_errors[request_id] = error
                event.set()
            self._inflight.clear()
        self._emit(BridgeEvent(name=BRIDGE_DOWN, sidecar_pid=pid, protocol_version=None))

    def _adopt_or_spawn(self, name: str, session_existed: bool) -> ChildHandle:
        if self._handoff is None or name not in DAEMON_STORES:
            existing = reattach(name, self.data_dir)
            return existing if existing is not None else self._spawn_child(name, self.data_dir)
        existing = reattach(name, self.data_dir)
        if (
            existing is not None
            and session_existed
            and self._session_id is not None
            and lease_still_valid(
                load_lease_meta(self.data_dir, name),
                pid=existing.pid,
                session=self._session_id,
                now=time.time(),
                ttl_seconds=self._lease_ttl,
            )
        ):
            return existing
        if existing is not None:
            terminate(existing)
        return self._spawn_bound(name)

    def _launch(self, name: str) -> ChildHandle:
        if self._handoff is None or name not in DAEMON_STORES:
            return self._spawn_child(name, self.data_dir)
        return self._spawn_bound(name)

    def _spawn_bound(self, name: str) -> ChildHandle:
        if self._handoff is None or self._session_id is None:
            raise BindingError("production lease handoff is not configured")
        store = DAEMON_STORES[name]
        handle = spawn(
            name,
            self.data_dir,
            lease_wait=True,
            supervisor_session=self._session_id,
        )
        try:
            lease = self._handoff.mint(
                store_name=store,
                daemon_name=name,
                data_dir=self.data_dir,
                pid=handle.pid,
                ttl_seconds=self._lease_ttl,
                supervisor_session=self._session_id,
            )
            self._deliver(handle, lease)
            save_lease_meta(
                self.data_dir,
                name,
                pid=handle.pid,
                session=self._session_id,
                expires_at=time.time() + self._lease_ttl,
            )
        except Exception:
            terminate(handle)
            pid_path(self.data_dir, name).unlink(missing_ok=True)
            raise
        return handle

    def _maintain_lease(self, name: str, handle: ChildHandle) -> None:
        """Renew on the private pipe, or respawn a reattached child before expiry.

        A child adopted after a supervisor restart has no stdin in this process.
        Reusing its old lease under a new session id is not a renewal. When the
        remaining TTL enters the renewal window, this starts a new PID on the
        current session instead.
        """
        if self._handoff is None or self._session_id is None or name not in DAEMON_STORES:
            return
        if handle.lease_stdin is not None:
            self._renew_if_due(name, handle)
            return
        if lease_still_valid(
            load_lease_meta(self.data_dir, name),
            pid=handle.pid,
            session=self._session_id,
            now=time.time(),
            ttl_seconds=self._lease_ttl,
        ):
            return
        terminate(handle)
        if self._stop.is_set():
            return
        try:
            replacement = self._launch(name)
        except Exception:
            return
        with self._mu:
            self._children[name] = replacement

    def _renew_if_due(self, name: str, handle: ChildHandle) -> None:
        if self._handoff is None or self._session_id is None or name not in DAEMON_STORES:
            return
        meta = load_lease_meta(self.data_dir, name)
        expires_at = meta.get("expires_at") if meta else None
        same_binding = (
            meta is not None
            and meta.get("pid") == handle.pid
            and meta.get("session") == self._session_id
            and isinstance(expires_at, (int, float))
            and not isinstance(expires_at, bool)
        )
        if not same_binding or not isinstance(expires_at, (int, float)):
            terminate(handle)
            return
        if expires_at - time.time() > renew_before(self._lease_ttl):
            return
        try:
            lease = self._handoff.mint(
                store_name=DAEMON_STORES[name],
                daemon_name=name,
                data_dir=self.data_dir,
                pid=handle.pid,
                ttl_seconds=self._lease_ttl,
                supervisor_session=self._session_id,
            )
            self._deliver(handle, lease)
            save_lease_meta(
                self.data_dir,
                name,
                pid=handle.pid,
                session=self._session_id,
                expires_at=time.time() + self._lease_ttl,
            )
        except Exception:
            terminate(handle)

    @staticmethod
    def _deliver(handle: ChildHandle, lease: str) -> None:
        stdin = handle.lease_stdin
        if stdin is None or not hasattr(stdin, "write"):
            raise BindingError(f"no private lease channel for {handle.name}")
        stdin.write(lease + "\n")
        stdin.flush()

    def _fail_start(self) -> None:
        with self._mu:
            handles = list(self._children.values())
            self._children.clear()
        for handle in handles:
            terminate(handle)
        self._lock.release()

    def _emit(self, event: BridgeEvent) -> None:
        with self._mu:
            self._events.append(event)
            listeners = list(self._listeners)
        for listener in listeners:
            listener(event)
