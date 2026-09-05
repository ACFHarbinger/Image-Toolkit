"""gui/src/thumbnails/scheduler.py
================================
Default ThumbnailScheduler: generation-tagged queue, no Qt (§1.2, #526).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from threading import Lock
from typing import Optional

from .order import order_visible_first


class DefaultThumbnailScheduler:
    """In-memory scheduler for fill-queue / cancel / generation tracking.

    Not a worker owner and not a Qt type. Galleries call ``take_next`` to
    decide *what* to load, then start their own workers. No queue-state
    signals — consumers inspect ``has_pending`` if they must.
    """

    def __init__(self, max_in_flight: int = 2) -> None:
        self._lock = Lock()
        self._generation = 0
        self._max_in_flight = max(1, int(max_in_flight))
        self._queue: deque[str] = deque()
        self._queued: set[str] = set()
        self._inflight: set[str] = set()

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def max_in_flight(self) -> int:
        return self._max_in_flight

    def is_current(self, generation: int) -> bool:
        return generation == self._generation

    def cancel(self) -> int:
        with self._lock:
            self._generation += 1
            self._queue.clear()
            self._queued.clear()
            self._inflight.clear()
            return self._generation

    def enqueue(
        self,
        paths: Sequence[str],
        *,
        visible: Optional[Sequence[str]] = None,
    ) -> None:
        ordered = order_visible_first(paths, visible)
        with self._lock:
            pending = self._queued | self._inflight
            for path in ordered:
                if path in pending:
                    continue
                self._queue.append(path)
                self._queued.add(path)
                pending.add(path)

    def take_next(self) -> Optional[str]:
        with self._lock:
            if len(self._inflight) >= self._max_in_flight:
                return None
            while self._queue:
                path = self._queue.popleft()
                self._queued.discard(path)
                if path in self._inflight:
                    continue
                self._inflight.add(path)
                return path
            return None

    def complete(self, path: str, generation: int) -> bool:
        with self._lock:
            self._inflight.discard(path)
            self._queued.discard(path)
            return generation == self._generation

    def has_pending(self) -> bool:
        with self._lock:
            return bool(self._queue or self._inflight)

    def queued_paths(self) -> tuple[str, ...]:
        """Queued (not yet in-flight) paths. Inspection only — no events."""
        with self._lock:
            return tuple(self._queue)
