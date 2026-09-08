from PySide6.QtGui import QImage

from gui.src.utils.cache.lru_image_cache import (
    DEFAULT_PIXMAP_BUDGET,
    LRU_CACHE_CEILING,
    LRUImageCache,
    PixmapBudget,
)


def _img() -> QImage:
    return QImage(1, 1, QImage.Format.Format_RGB32)


def test_resize_shrink_evicts_lru_entries(q_app):
    cache = LRUImageCache(maxsize=5)
    for i in range(5):
        cache[f"k{i}"] = _img()

    cache.get("k0")  # k0 is now most-recently-used
    cache.resize(2)

    assert cache.maxsize == 2
    assert len(cache) == 2
    assert "k0" in cache
    assert "k4" in cache
    assert "k1" not in cache


def test_resize_grow_keeps_entries(q_app):
    cache = LRUImageCache(maxsize=2)
    cache["a"] = _img()
    cache["b"] = _img()

    cache.resize(10)

    assert cache.maxsize == 10
    assert len(cache) == 2
    cache["c"] = _img()
    assert len(cache) == 3


def test_setitem_still_evicts_after_resize(q_app):
    cache = LRUImageCache(maxsize=5)
    for i in range(5):
        cache[f"k{i}"] = _img()

    cache.resize(2)
    cache["new"] = _img()

    assert len(cache) == 2
    assert "new" in cache
    assert "k4" in cache
    assert "k3" not in cache


def test_pixmap_budget_defaults_match_current_sizes():
    budget = DEFAULT_PIXMAP_BUDGET
    assert budget.card_thumb == 250
    assert budget.single_gallery == 300
    assert budget.two_galleries_selected == 200
    assert budget.two_galleries_found == 300
    assert budget.virtual_dual_shared == 500
    assert budget.virtual_model == 300
    assert budget.ceiling == LRU_CACHE_CEILING == 800


def test_pixmap_budget_clamp_respects_ceiling():
    budget = DEFAULT_PIXMAP_BUDGET
    assert budget.clamp(100) == 100
    assert budget.clamp(budget.ceiling) == budget.ceiling
    assert budget.clamp(budget.ceiling + 1) == budget.ceiling
    assert budget.clamp(999999) == budget.ceiling
    tight = PixmapBudget(ceiling=10)
    assert tight.clamp(50) == 10


def test_caches_constructed_from_budget_fields():
    budget = DEFAULT_PIXMAP_BUDGET
    assert LRUImageCache(maxsize=budget.card_thumb).maxsize == 250
    assert LRUImageCache(maxsize=budget.single_gallery).maxsize == 300
    assert LRUImageCache(maxsize=budget.two_galleries_selected).maxsize == 200
    assert LRUImageCache(maxsize=budget.two_galleries_found).maxsize == 300
    assert LRUImageCache(maxsize=budget.virtual_dual_shared).maxsize == 500
    assert LRUImageCache(maxsize=budget.virtual_model).maxsize == 300


def test_per_cache_defaults_sum_is_documented():
    budget = DEFAULT_PIXMAP_BUDGET
    total = (
        budget.card_thumb
        + budget.single_gallery
        + budget.two_galleries_selected
        + budget.two_galleries_found
        + budget.virtual_dual_shared
        + budget.virtual_model
    )
    # Six independent caches: 250+300+200+300+500+300. Each clamps to
    # ceiling on its own; the sum is not required to be <= ceiling.
    assert total == 1850
    assert total > budget.ceiling
