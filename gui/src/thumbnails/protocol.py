"""gui/src/thumbnails/protocol.py
================================
Shared scheduling/cancellation/generation-tracking contract (§1.2, #526).

Interface-only. Each gallery keeps its own pagination and rendering;
unification onto one implementation is Phase 2 (#531). Queue state stays
encapsulated — no EventHub / status-bar broadcast in this pass.
"""

from __future__ import annotations

from typing import Optional, Protocol, Sequence, runtime_checkable


@runtime_checkable
class ThumbnailScheduler(Protocol):
    """Bounded visible-first thumbnail queue with generation-tagged cancel.

    Galleries dispatch workers themselves (this protocol does not own
    QThreadPool / ImageLoaderWorker). A generation bump invalidates every
    in-flight take; callers drop stale deliveries with ``is_current``.
    """

    @property
    def generation(self) -> int: ...

    @property
    def max_in_flight(self) -> int: ...

    def is_current(self, generation: int) -> bool:
        """True iff *generation* is still the scheduler's live generation."""
        ...

    def cancel(self) -> int:
        """Drop the queue, forget in-flight paths, bump generation.

        Returns the new generation. Does not stop workers — the gallery
        drains its pool after calling this.
        """
        ...

    def enqueue(
        self,
        paths: Sequence[str],
        *,
        visible: Optional[Sequence[str]] = None,
    ) -> None:
        """Queue *paths* not already pending. Visible paths are taken first."""
        ...

    def take_next(self) -> Optional[str]:
        """Pop the next path if under the concurrency cap, else None."""
        ...

    def complete(self, path: str, generation: int) -> bool:
        """Mark *path* finished. Returns True iff *generation* is still live."""
        ...

    def has_pending(self) -> bool:
        """True if queued or in-flight paths remain."""
        ...
