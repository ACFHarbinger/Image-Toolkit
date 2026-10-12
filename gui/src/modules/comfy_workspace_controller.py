"""Shared ComfyUI lifecycle; browser launch never changes server ownership."""
from __future__ import annotations

import threading
from collections.abc import Callable

from backend.src.constants.comfy import ServerState, ViewState
from backend.src.models.core.comfy_manager import ComfyUIManager
from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from gui.src.helpers.base import BaseQThreadWorker
from gui.src.helpers.worker_retention import retain_until_stopped


class _Operation(BaseQThreadWorker):
    def __init__(self, action: Callable[[], object]) -> None:
        super().__init__()
        self._action = action

    def _execute(self) -> object:
        return self._action()


class ComfyWorkspaceController(QObject):
    """One service coordinator shared by legacy and future Guided/Graph views.

    External-only v1 never creates a renderer. Successful OS browser dispatch
    is deliberately not reported as Displayed: we cannot observe that browser.
    """

    server_state_changed = Signal(object)
    view_state_changed = Signal(object)
    busy_changed = Signal(bool)
    error = Signal(str)
    log_line = Signal(str)
    browser_opened = Signal(str)
    run_record_changed = Signal(object)
    object_info_changed = Signal(object)
    _instance: ComfyWorkspaceController | None = None
    tier = "external-only"

    @classmethod
    def instance(cls) -> ComfyWorkspaceController:
        if cls._instance is None:
            cls._instance = cls(parent=QApplication.instance())
            app = QApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(cls._instance.shutdown)
        return cls._instance

    def __init__(self, manager=None, parent=None, opener=None) -> None:
        super().__init__(parent)
        self.manager = manager if manager is not None else ComfyUIManager.instance()
        self.view_state = ViewState.NOT_CREATED
        self._opener = opener or QDesktopServices.openUrl
        self._worker: _Operation | None = None
        self._cancel = threading.Event()
        self._pending_stop = False
        self._closed = False
        self.manager.subscribe_state(self._publish_state)
        self.manager.subscribe_log(self._publish_log)
        # Run records arrive on the provenance poller or queue-worker thread;
        # emitting here hands them to GUI-thread receivers via queued
        # connections (#737, consumed by #739/#752).
        subscribe_runs = getattr(self.manager, "subscribe_runs", None)
        if subscribe_runs is not None:
            subscribe_runs(self._publish_run)
        # Pre-flight validation cache (#738): fetched on a worker thread at
        # Ready; None after retries means unavailable (GUI fails open).
        subscribe_object_info = getattr(self.manager, "subscribe_object_info", None)
        if subscribe_object_info is not None:
            subscribe_object_info(self._publish_object_info)
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._probe)
        self._timer.start()

    @property
    def server_state(self) -> ServerState:
        return self.manager.state

    @property
    def busy(self) -> bool:
        return self._worker is not None

    def _publish_state(self, state: ServerState) -> None:
        if not self._closed:
            self.server_state_changed.emit(state)

    def _publish_log(self, line: str) -> None:
        if not self._closed:
            self.log_line.emit(line)

    def _publish_run(self, record) -> None:
        if not self._closed:
            self.run_record_changed.emit(record)

    def _publish_object_info(self, info) -> None:
        if not self._closed:
            self.object_info_changed.emit(info)

    def _submit(self, action: Callable[[], object]) -> bool:
        if self._closed or self.busy:
            return False
        worker = _Operation(action)
        self._worker = worker
        worker.finished.connect(self._done)
        worker.error.connect(self._failed)
        self.busy_changed.emit(True)
        worker.start()
        retain_until_stopped(worker)
        return True

    @Slot(object)
    def _failed(self, exc) -> None:
        if not self._closed:
            self.error.emit(str(exc))

    @Slot(object)
    def _done(self, _result) -> None:
        self._worker = None
        if self._closed:
            return
        self.busy_changed.emit(False)
        self.server_state_changed.emit(self.server_state)
        if self._pending_stop:
            self._pending_stop = False
            self.stop()

    def run_http_action(self, action: Callable[[], object]) -> bool:
        """Serialize HTTP submissions with lifecycle changes, off the GUI thread."""
        if self.server_state != ServerState.READY:
            return False
        if self.busy or self._closed:
            return False
        self._cancel.clear()
        return self._submit(action)

    def start(self, port: int = 8188, enable_manager: bool = False) -> None:
        if self.busy or self._closed:
            return
        self._cancel.clear()

        def launch() -> None:
            self.manager.start(port, enable_manager=enable_manager)
            if not self.manager.wait_until_ready(timeout=120, cancel=self._cancel) and not self._cancel.is_set():
                raise RuntimeError("ComfyUI did not become ready. Check the server log.")

        self._submit(launch)

    def connect(self, port: int = 8188) -> None:
        def attach() -> None:
            if not self.manager.connect(port):
                raise RuntimeError("No ComfyUI server responded on the selected local port.")
        self._submit(attach)

    def stop(self) -> None:
        """Stop only an owned process; externally started servers are detached."""
        self._cancel.set()
        if self.busy:
            self._pending_stop = True
            return
        self._submit(self.manager.stop)

    def _probe(self) -> None:
        if self.server_state in (ServerState.READY, ServerState.DISCONNECTED):
            self._submit(self.manager.refresh_state)

    def open_external(self) -> bool:
        if self._closed or self.server_state != ServerState.READY:
            return False
        try:
            opened = bool(self._opener(QUrl(self.manager.url)))
        except Exception as exc:
            self.error.emit(str(exc))
            return False
        if opened:
            self.browser_opened.emit(self.manager.url)
        else:
            self.error.emit("Could not open the system browser. Copy the server URL to a browser.")
        return opened

    def shutdown(self) -> None:
        """Application shutdown, not tab navigation: cancel startup then stop our process."""
        if self._closed:
            return
        self._closed = True
        self._timer.stop()
        self._cancel.set()
        worker = self._worker
        manager = self.manager

        def finish() -> None:
            if worker is not None:
                worker.wait()
            manager.stop()

        threading.Thread(target=finish, name="comfy-shutdown", daemon=False).start()
