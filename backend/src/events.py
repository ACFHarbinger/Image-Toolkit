"""Non-Qt publish/subscribe primitive for backend-to-GUI event delivery.

Issue #529 (D7): the ``QObject``/``Signal``-based classes under
``backend/src/web/`` must not depend on Qt — a crawler thread must never
touch a GUI-owned Qt object, the crash class behind this repo's documented
``QSocketNotifier`` SIGSEGV. ``Observable`` is the backend side of that
contract: a tiny thread-safe callback registry with zero Qt imports. The
GUI layer adapts it to real Qt signals at the boundary via
``gui.src.qt_event_bridge.QtEventBridge`` (which queues onto the GUI
thread), never the other way around.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Generic, TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")


class Observable(Generic[T]):
    """Thread-safe single-payload event channel with zero Qt dependency.

    Subscribers are plain callables invoked synchronously on the
    publisher's thread — cross-thread delivery (e.g. onto the Qt GUI
    thread) is the GUI adapter's job, not this class's. Publishing takes
    a snapshot under an ``RLock``; a raising subscriber is logged and
    skipped so one bad listener cannot kill the emitting (crawler) thread.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._callbacks: dict[int, Callable[[T], None]] = {}
        self._next_token = 0

    def subscribe(self, callback: Callable[[T], None]) -> Callable[[], None]:
        """Register *callback*; returns an idempotent-feeling unsubscribe closure."""
        with self._lock:
            token = self._next_token
            self._next_token += 1
            self._callbacks[token] = callback

        def unsubscribe() -> None:
            with self._lock:
                self._callbacks.pop(token, None)

        return unsubscribe

    def publish(self, event: T) -> None:
        """Deliver *event* to every subscriber at call time."""
        with self._lock:
            callbacks = tuple(self._callbacks.values())
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                log.exception("Observable subscriber raised; skipping")
