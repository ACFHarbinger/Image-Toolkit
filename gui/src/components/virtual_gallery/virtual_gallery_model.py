"""Virtualized (lazy) thumbnail gallery model — GUI/UX §2.1 Option A.

The current page-based galleries materialize one ``QLabel`` card widget per
image inside a ``QGridLayout`` and cap the page size (100 cards for the
database listings, ``found_page_size`` elsewhere). That bounded-page approach
keeps widget count fixed but still rebuilds every card on every page turn and
reloads thumbnails on LRU eviction, which is what the §2.1 updates since
2026-08-19 kept tuning around (issues #444/#445/#447/#453/#454/#456/#458).

This model is the Option A rewrite of the *card surface*: instead of owning a
widget per path, it exposes every path as a row of a ``QAbstractListModel``
and serves a lazily-loaded thumbnail as ``Qt.DecorationRole``. Qt's
``QListView`` viewport culling means only visible cells ever request a
decoration, so a 100k-row gallery costs the same in widget/paint terms as a
100-row one — no page cap, no per-page widget rebuild.

Thumbnails are loaded on a dedicated ``QThreadPool`` by the same
``ImageLoaderWorker`` the QLabel galleries use, stored in a bounded
``LRUImageCache`` (QImage, never QPixmap — same RAM rationale as
``LRUImageCache``'s docstring), and each successful load emits ``dataChanged``
for its row so the view repaints just that cell. Loads are generation-tagged
and stale deliveries (from before a ``set_paths``/``cancel_loading``) are
dropped, mirroring the gallery base classes' ``_load_generation`` protocol.
"""

from __future__ import annotations

import os
from typing import List, Optional

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QThreadPool
from PySide6.QtGui import QIcon, QImage, QPixmap
from shiboken6 import Shiboken

from gui.src.utils.cache.lru_image_cache import LRUImageCache


class VirtualGalleryModel(QAbstractListModel):
    """Expose a list of file paths as lazily-decorated, virtualized rows.

    The model never creates a widget per row; it only ever (a) answers
    ``rowCount()`` for the full path list and (b) answers ``data()`` for rows
    the view actually needs, scheduling a background thumbnail load on first
    ``Qt.DecorationRole`` request. ``worker_factory`` is injectable so tests
    can substitute a deterministic loader.
    """

    # Row roles beyond Qt's built-ins.
    PathRole = Qt.ItemDataRole.UserRole

    def __init__(
        self,
        parent=None,
        cache_maxsize: int = 300,
        worker_factory=None,
        shared_cache: Optional[LRUImageCache] = None,
    ):
        super().__init__(parent)
        self._paths: List[str] = []
        self._cache = shared_cache if shared_cache is not None else LRUImageCache(maxsize=cache_maxsize)
        self._loading: set[str] = set()
        self._failed: set[str] = set()
        self._active_workers: set = set()
        self._generation: int = 0

        self.thumbnail_size: int = 180
        # Deferred: gui.src.helpers pulls a heavy chain (windows -> settings ->
        # asp_backend) that needs the submodule bootstrap; only resolve it when
        # a model is actually constructed (app/tests always have the bootstrap).
        if worker_factory is None:
            from gui.src.helpers import ImageLoaderWorker

            worker_factory = ImageLoaderWorker
        self.worker_factory = worker_factory
        # Dedicated per-model pool, capped like AbstractGalleryBase's (a
        # gallery per tab must not spawn N * cpu_count threads).
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(max(2, min(8, os.cpu_count() or 4)))

        self._placeholder_pixmap: Optional[QPixmap] = None

    # ------------------------------------------------------------------
    # Public data API (mirrors the tab-facing bits of the QLabel galleries)
    # ------------------------------------------------------------------

    def set_paths(self, paths) -> None:
        """Replace the whole item list. In-flight loads become stale."""
        self._generation += 1
        self.beginResetModel()
        self._paths = list(paths)
        self._loading.clear()
        self._failed.clear()
        # The pool keeps queued/running runnables alive, so dropping the refs
        # here only releases finished workers; their late deliveries are
        # rejected by the generation check below.
        self._active_workers.clear()
        self.endResetModel()

    def clear(self) -> None:
        self.set_paths([])

    def rowCount(self, parent=None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._paths)

    def path_at(self, row: int) -> Optional[str]:
        if 0 <= row < len(self._paths):
            return self._paths[row]
        return None

    def row_for_path(self, path: str) -> int:
        try:
            return self._paths.index(path)
        except ValueError:
            return -1

    def set_thumbnail_size(self, size: int) -> None:
        """Change the served decoration size; cached QImages are rescaled on
        access, so zooming never reloads from disk. Emits ``layoutChanged``
        so the view re-lays-out with the new grid size."""
        size = max(32, int(size))
        if size == self.thumbnail_size:
            return
        self.thumbnail_size = size
        self._placeholder_pixmap = None
        self.layoutChanged.emit()

    def clear_cache(self) -> None:
        self._cache.clear()

    def cached_image(self, path: str):
        """Return the cached QImage for *path* (None if not loaded yet). Used
        by tabs that also render the loaded thumbnail outside the gallery
        (e.g. a merge canvas or queue strip)."""
        return self._cache.get(path)

    def cancel_loading(self) -> None:
        """Drop all queued/in-flight loads. Workers already on the pool finish
        but their results are rejected as stale via the generation check."""
        self._generation += 1
        self._loading.clear()
        self._failed.clear()
        self._active_workers.clear()

    def prefetch(self, path: str) -> None:
        """Schedule a background thumbnail load for *path* if it isn't cached,
        loading, or already failed — used by the view's scroll prefetch."""
        self._ensure_loading(path)

    # ------------------------------------------------------------------
    # QAbstractListModel
    # ------------------------------------------------------------------

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._paths)):
            return None
        path = self._paths[index.row()]
        if role == Qt.ItemDataRole.DecorationRole:
            return self._decoration_for(path)
        if role == Qt.ItemDataRole.ToolTipRole:
            return os.path.basename(path)
        if role == self.PathRole:
            return path
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsDragEnabled
        )

    # ------------------------------------------------------------------
    # Lazy decoration + background loading
    # ------------------------------------------------------------------

    def _decoration_for(self, path: str) -> QIcon:
        cached = self._cache.get(path)
        if cached is not None and not cached.isNull():
            return QIcon(self._to_pixmap(cached))
        self._ensure_loading(path)
        return QIcon(self._placeholder())

    def _to_pixmap(self, qimage: QImage) -> QPixmap:
        pixmap = QPixmap.fromImage(qimage)
        size = self.thumbnail_size
        if pixmap.width() > size or pixmap.height() > size:
            return pixmap.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return pixmap

    def _placeholder(self) -> QPixmap:
        if self._placeholder_pixmap is None or self._placeholder_pixmap.isNull():
            size = self.thumbnail_size
            pm = QPixmap(size, size)
            pm.fill(Qt.GlobalColor.transparent)
            self._placeholder_pixmap = pm
        return self._placeholder_pixmap

    def _ensure_loading(self, path: str) -> None:
        if path in self._cache or path in self._loading or path in self._failed:
            return
        self._loading.add(path)
        gen = self._generation
        worker = self.worker_factory(path, self.thumbnail_size)
        worker.load_generation = gen
        worker.signals.result.connect(
            lambda p, img, g=gen: self._on_thumbnail_loaded(p, img, g)
        )
        self._active_workers.add(worker)
        self.thread_pool.start(worker)

    def _on_thumbnail_loaded(self, path: str, image, generation: int) -> None:
        # Queued (cross-thread) signal may arrive after the model's QObject
        # is torn down; sender() on a dead QObject segfaults rather than
        # raising (same guard the QLabel galleries use).
        if not Shiboken.isValid(self):
            return
        # Drop the worker's strong ref first so stale deliveries (and the
        # failure path below) don't leak entries in _active_workers.
        sender = self.sender()
        if sender is not None:
            for worker in list(self._active_workers):
                if getattr(worker, "signals", None) is sender:
                    self._active_workers.discard(worker)
                    break
        if generation != self._generation:
            self._loading.discard(path)
            return
        if image is None or (isinstance(image, QImage) and image.isNull()):
            self._failed.add(path)
            self._loading.discard(path)
            return
        if not isinstance(image, QImage):
            image = QImage(image)
            if image.isNull():
                self._failed.add(path)
                self._loading.discard(path)
                return
        self._cache[path] = image
        self._loading.discard(path)
        row = self.row_for_path(path)
        if row >= 0:
            self.dataChanged.emit(
                self.index(row, 0),
                self.index(row, 0),
                [Qt.ItemDataRole.DecorationRole],
            )


__all__ = ["VirtualGalleryModel"]
