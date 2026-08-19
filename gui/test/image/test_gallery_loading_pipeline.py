"""#444 regressions: single-signal batch rendering, one drain per refresh
cycle, and page-sized LRU caches.
"""

import pytest
from PySide6.QtCore import QObject, QRunnable, Signal
from PySide6.QtGui import QImage

from gui.test.image.test_gallery_classes import ConcreteSingleGallery, ConcreteTwoGalleries

pytestmark = pytest.mark.gui


class _FakeSignals(QObject):
    result = Signal(str, QImage)
    batch_result = Signal(list, list)


class _FakeBatchWorker(QRunnable):
    """Stand-in for BatchImageLoaderWorker: same signal surface, run() is a
    no-op so tests control emission deterministically."""

    def __init__(self, paths, target_size):
        super().__init__()
        self.paths = paths
        self.target_size = target_size
        self.signals = _FakeSignals()
        self.stopped = False

    def stop(self):
        self.stopped = True

    def run(self):
        pass


class _FakePool:
    """Records dispatches/drains instead of running anything."""

    def __init__(self):
        self.started = []
        self.wait_calls = 0
        self.active = 0

    def start(self, worker):
        self.started.append(worker)

    def clear(self):
        pass

    def activeThreadCount(self):
        return self.active

    def waitForDone(self, timeout=None):
        self.wait_calls += 1
        return True


def _img() -> QImage:
    img = QImage(10, 10, QImage.Format.Format_RGB32)
    img.fill(0xFF336699)
    return img


@pytest.fixture
def single_gallery(q_app):
    gallery = ConcreteSingleGallery()
    gallery.thread_pool = _FakePool()
    return gallery


@pytest.fixture
def two_galleries(q_app):
    gallery = ConcreteTwoGalleries()
    gallery.thread_pool = _FakePool()
    return gallery


class TestSingleSignalRendering:
    def test_batch_load_renders_each_card_once(self, single_gallery):
        gallery = single_gallery
        paths = ["a.jpg", "b.jpg"]
        for p in paths:
            gallery.path_to_card_widget[p] = gallery.create_card_widget(p, None)
        gallery._loading_paths.update(paths)

        calls = []
        original = gallery.update_card_pixmap

        def spy(widget, pixmap, label_ref=None):
            calls.append(widget)
            return original(widget, pixmap, label_ref)

        gallery.update_card_pixmap = spy

        gallery._trigger_batch_found_load(paths)
        worker = gallery.thread_pool.started[0]
        # Mimic the real worker: per-path result emits, then the batch emit.
        # Only batch_result is connected, so each card renders exactly once.
        for p in paths:
            worker.signals.result.emit(p, _img())
        worker.signals.batch_result.emit([(p, _img()) for p in paths], paths)

        assert len(calls) == len(paths)

    def test_two_galleries_batch_load_renders_each_card_once(self, two_galleries):
        gallery = two_galleries
        paths = ["a.jpg", "b.jpg"]
        for p in paths:
            gallery.path_to_label_map[p] = gallery.create_card_widget(p, None, False)
        gallery.found_loading_paths.update(paths)

        calls = []
        original = gallery.update_card_pixmap

        def spy(widget, pixmap):
            calls.append(widget)
            return original(widget, pixmap)

        gallery.update_card_pixmap = spy

        gallery._trigger_batch_found_load(paths)
        worker = gallery.thread_pool.started[0]
        for p in paths:
            worker.signals.result.emit(p, _img())
        worker.signals.batch_result.emit([(p, _img()) for p in paths], paths)

        assert len(calls) == len(paths)


class TestDrainGuard:
    def test_second_cancel_in_cycle_skips_drain(self, single_gallery):
        gallery = single_gallery
        pool = gallery.thread_pool

        gallery._active_workers.add(_FakeBatchWorker(["x.jpg"], 180))
        pool.active = 1
        gallery.cancel_loading()
        assert pool.wait_calls == 1

        # refresh_gallery_view() then clear_gallery_widgets(): the pool is
        # already idle and nothing is tracked, so no second drain.
        pool.active = 0
        gallery.cancel_loading()
        assert pool.wait_calls == 1
        assert gallery._load_generation == 2

    def test_cancel_with_running_worker_still_drains(self, single_gallery):
        gallery = single_gallery
        pool = gallery.thread_pool

        pool.active = 1  # untracked but pool-busy -> conservative full path
        gallery.cancel_loading()
        assert pool.wait_calls == 1

    def test_two_galleries_second_cancel_in_cycle_skips_drain(self, two_galleries):
        gallery = two_galleries
        pool = gallery.thread_pool

        gallery._active_workers.add(_FakeBatchWorker(["x.jpg"], 180))
        pool.active = 1
        gallery.cancel_loading()
        assert pool.wait_calls == 1

        # start_loading_thumbnails() cancels, refresh_found_gallery() cancels
        # again within the same scan cycle.
        pool.active = 0
        gallery.cancel_loading()
        assert pool.wait_calls == 1
        assert gallery._load_generation == 2


class TestCacheSizing:
    def test_single_cache_sized_to_page_size(self, single_gallery):
        gallery = single_gallery
        gallery.page_size = 1000
        gallery.start_loading_gallery([f"p{i}.jpg" for i in range(1500)])
        assert gallery._initial_pixmap_cache.maxsize == 1000

    def test_single_cache_all_page_capped_at_path_count(self, single_gallery):
        gallery = single_gallery
        gallery.page_size = 999999  # "All"
        gallery.start_loading_gallery([f"p{i}.jpg" for i in range(400)])
        assert gallery._initial_pixmap_cache.maxsize == 400

    def test_single_cache_keeps_larger_configured_baseline(self, single_gallery):
        gallery = single_gallery
        gallery._initial_pixmap_cache.resize(2000)  # §2.16B user preference
        gallery.page_size = 100
        gallery.start_loading_gallery([f"p{i}.jpg" for i in range(50)])
        assert gallery._initial_pixmap_cache.maxsize == 2000

    def test_found_cache_sized_to_page_size(self, two_galleries):
        gallery = two_galleries
        gallery.found_page_size = 500
        gallery.start_loading_thumbnails([f"p{i}.jpg" for i in range(800)])
        assert gallery._found_pixmap_cache.maxsize == 500

    def test_selected_cache_sized_to_page_size(self, two_galleries):
        gallery = two_galleries
        gallery.selected_page_size = 250
        gallery.selected_files = [f"p{i}.jpg" for i in range(300)]
        gallery.refresh_selected_panel()
        assert gallery._selected_pixmap_cache.maxsize == 250
