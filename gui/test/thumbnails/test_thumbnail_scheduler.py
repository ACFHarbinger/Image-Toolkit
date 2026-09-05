"""gui/test/thumbnails/test_thumbnail_scheduler.py
===============================================
Contract tests for ThumbnailScheduler (§1.2, #526).

No Qt — the scheduler is a plain-Python queue with generation tracking.
"""

from __future__ import annotations

from gui.src.thumbnails import (
    DefaultThumbnailScheduler,
    ThumbnailScheduler,
    order_visible_first,
)


class TestOrderVisibleFirst:
    def test_empty_and_noop(self):
        assert order_visible_first([]) == []
        assert order_visible_first(["a", "b"], visible=None) == ["a", "b"]
        assert order_visible_first(["a", "b"], visible=[]) == ["a", "b"]

    def test_visible_stable_prefix(self):
        paths = ["a", "b", "c", "d", "e"]
        assert order_visible_first(paths, visible=["d", "b"]) == [
            "b",
            "d",
            "a",
            "c",
            "e",
        ]

    def test_visible_not_in_paths_ignored(self):
        assert order_visible_first(["a", "b"], visible=["z", "b"]) == ["b", "a"]


class TestDefaultThumbnailScheduler:
    def test_satisfies_protocol(self):
        scheduler = DefaultThumbnailScheduler(max_in_flight=2)
        assert isinstance(scheduler, ThumbnailScheduler)

    def test_visible_first_take_order(self):
        scheduler = DefaultThumbnailScheduler(max_in_flight=2)
        paths = [f"/p/{i:04d}.png" for i in range(10)]
        visible = [paths[7], paths[8]]
        scheduler.enqueue(paths, visible=visible)
        assert scheduler.take_next() == paths[7]
        assert scheduler.take_next() == paths[8]
        # Cap reached — nothing more until complete().
        assert scheduler.take_next() is None
        assert scheduler.has_pending()

    def test_complete_releases_slot_and_preserves_order(self):
        scheduler = DefaultThumbnailScheduler(max_in_flight=1)
        scheduler.enqueue(["/a.png", "/b.png", "/c.png"])
        gen = scheduler.generation
        assert scheduler.take_next() == "/a.png"
        assert scheduler.complete("/a.png", gen) is True
        assert scheduler.take_next() == "/b.png"

    def test_cancel_bumps_generation_and_drops_queue(self):
        scheduler = DefaultThumbnailScheduler(max_in_flight=2)
        gen0 = scheduler.generation
        scheduler.enqueue(["/a.png", "/b.png"])
        taken = scheduler.take_next()
        assert taken == "/a.png"
        gen1 = scheduler.cancel()
        assert gen1 == gen0 + 1
        assert scheduler.is_current(gen0) is False
        assert scheduler.take_next() is None
        assert scheduler.has_pending() is False
        assert scheduler.complete("/a.png", gen0) is False

    def test_enqueue_skips_already_pending(self):
        scheduler = DefaultThumbnailScheduler(max_in_flight=2)
        scheduler.enqueue(["/a.png", "/b.png"])
        scheduler.enqueue(["/a.png", "/c.png"])
        assert scheduler.queued_paths() == ("/a.png", "/b.png", "/c.png")

    def test_stale_complete_does_not_revive_cancelled_queue(self):
        scheduler = DefaultThumbnailScheduler(max_in_flight=1)
        scheduler.enqueue(["/a.png"])
        gen = scheduler.generation
        scheduler.take_next()
        scheduler.cancel()
        scheduler.enqueue(["/b.png"])
        assert scheduler.complete("/a.png", gen) is False
        assert scheduler.take_next() == "/b.png"
