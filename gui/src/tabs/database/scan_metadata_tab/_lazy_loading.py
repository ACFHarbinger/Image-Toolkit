"""Lazy thumbnail loading for ``ScanMetadataTab``.

Superseded by the virtual gallery's scroll prefetch (GUI/UX §2.1 Option A):
the model schedules background loads for the visible viewport ± buffer itself.
These slots are kept as no-ops so the old scroll/lazy-load plumbing can't
touch the removed grid widgets.
"""

from __future__ import annotations


class _LazyLoadingMixin:
    """No-op lazy-load overrides (the virtual gallery prefetches)."""

    def _on_scroll_event(self, value):
        """Virtual gallery prefetch handles scrolling; nothing to do."""

    def _process_visible_items(self):
        """Virtual gallery prefetch handles visibility; nothing to do."""

    def _start_lazy_batch(self, paths: list):
        """Kept for API compatibility; never called now."""

    def _start_image_loading_pool(self, paths_to_load: list):
        """Kept for API compatibility; never called now."""

    def on_single_image_loaded(self, path: str, pixmap):
        """Kept for API compatibility; never called now."""

    def _finalize_batch_loading(self):
        """Kept for API compatibility; never called now."""


__all__ = ["_LazyLoadingMixin"]


__all__ = ["_LazyLoadingMixin"]
