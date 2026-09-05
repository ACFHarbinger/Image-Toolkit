"""Qt adapter for backend :class:`~backend.src.events.Observable` channels.

Issue #529 (D7): backend classes under ``backend/src/web/`` publish plain
(non-Qt) events, potentially from worker threads. A crawler thread must
never invoke a GUI slot directly (this repo's ``QSocketNotifier`` SIGSEGV
crash class). ``QtEventBridge`` is the single allowed crossing point: it is
constructed on the GUI thread, and every published event is re-emitted
through a ``Signal(object)`` wired with ``Qt.QueuedConnection`` so delivery
always runs on the GUI thread.

Threading contract: construct on the GUI thread (never inside
``QThread.run()``/``QRunnable.run()`` — that would instantiate a ``QObject``
off the GUI thread, the exact failure this exists to prevent); ``attach``,
``detach`` and the subscribed ``post`` entry point are safe from any thread.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, Qt, Signal, Slot


class QtEventBridge(QObject):
    """Forward one backend ``Observable`` to a GUI-thread handler."""

    _incoming = Signal(object)

    def __init__(
        self,
        handle_event: Callable[[Any], None],
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._handle_event = handle_event
        self._unsubscribe: Optional[Callable[[], None]] = None
        self._incoming.connect(
            self._deliver, Qt.ConnectionType.QueuedConnection
        )

    def attach(self, observable: Any) -> None:
        """Subscribe ``post`` to *observable*, replacing any prior subscription."""
        self.detach()
        self._unsubscribe = observable.subscribe(self.post)

    def detach(self) -> None:
        """Drop the current subscription, if any. Safe to call repeatedly."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def post(self, event: Any) -> None:
        """Publish-side entry point. Safe from any worker thread."""
        self._incoming.emit(event)

    @Slot(object)
    def _deliver(self, event: Any) -> None:
        """Runs on the GUI thread (queued connection)."""
        self._handle_event(event)
