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
from collections import deque
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
    InDbRole = Qt.ItemDataRole.UserRole + 1
    SelectedRole = Qt.ItemDataRole.UserRole + 2
    PreviewRole = Qt.ItemDataRole.UserRole + 3
    RatingRole = Qt.ItemDataRole.UserRole + 4
    ResolutionRole = Qt.ItemDataRole.UserRole + 5
    FormatRole = Qt.ItemDataRole.UserRole + 6
    StarRatingRole = Qt.ItemDataRole.UserRole + 7
    TagCountRole = Qt.ItemDataRole.UserRole + 8

    def __init__(
        self,
        parent=None,
        cache_maxsize: int = 300,
        worker_factory=None,
        shared_cache: Optional[LRUImageCache] = None,
        fill_mode: bool = True,
        fill_limit: Optional[int] = None,
        max_concurrent_loads: int = 2,
    ):
        super().__init__(parent)
        self._paths: List[str] = []
        self._cache = shared_cache if shared_cache is not None else LRUImageCache(maxsize=cache_maxsize)
        self._loading: set[str] = set()
        self._failed: set[str] = set()
        self._in_db: set[str] = set()
        self._selected: set[str] = set()
        self._preview: set[str] = set()
        self._ratings: dict[str, str] = {}
        self._resolutions: dict[str, tuple[int, int]] = {}
        self._formats: dict[str, str] = {}
        self._star_ratings: dict[str, float] = {}
        self._tag_counts: dict[str, int] = {}
        self._active_workers: set = set()
        self._generation: int = 0

        # Background fill warms every row so a directory's thumbnails remain
        # available even before the user scrolls to them. Dispatch is tightly
        # bounded below; callers can select a lower limit for crash-sensitive
        # native decoder surfaces such as Wallpaper.
        self.fill_mode = bool(fill_mode)
        self.fill_limit = fill_limit
        self._fill_max_in_flight = max(1, int(max_concurrent_loads))
        self._fill_queue: deque = deque()

        self.thumbnail_size: int = 180
        # Deferred: gui.src.helpers pulls a heavy chain (windows -> settings ->
        # asp_backend) that needs the submodule bootstrap; only resolve it when
        # a model is actually constructed (app/tests always have the bootstrap).
        if worker_factory is None:
            from gui.src.helpers import ImageLoaderWorker

            worker_factory = ImageLoaderWorker
        self.worker_factory = worker_factory
        # A virtual gallery can have many rows but only a small visible
        # surface. The caller controls the small concurrency ceiling.
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(self._fill_max_in_flight)

        self._placeholder_pixmap: Optional[QPixmap] = None

    # ------------------------------------------------------------------
    # Public data API (mirrors the tab-facing bits of the QLabel galleries)
    # ------------------------------------------------------------------

    def set_paths(self, paths) -> None:
        """Replace the whole item list. In-flight loads become stale."""
        self._generation += 1
        self._cancel_workers()
        self.beginResetModel()
        self._paths = list(paths)
        self._loading.clear()
        self._failed.clear()
        # The pool keeps queued/running runnables alive, so dropping the refs
        # here only releases finished workers; their late deliveries are
        # rejected by the generation check below.
        self._active_workers.clear()
        self._fill_queue.clear()
        self.endResetModel()
        if self.fill_mode:
            self._fill_all()

    def _fill_all(self) -> None:
        """Queue every not-yet-cached path for a continuous background load."""
        gen = self._generation
        paths = [
            p for p in self._paths
            if p not in self._cache and p not in self._loading and p not in self._failed
        ]
        if self.fill_limit is not None:
            paths = paths[: self.fill_limit]
        if not paths:
            return
        self._loading.update(paths)
        self._fill_queue.extend(paths)
        for _ in range(self._fill_max_in_flight):
            self._dispatch_fill(gen)

    def _dispatch_fill(self, gen: int) -> None:
        """Dispatch the next queued fill path (chained on completion)."""
        if gen != self._generation or not self._fill_queue:
            return
        path = self._fill_queue.popleft()
        worker = self.worker_factory(path, self.thumbnail_size)
        worker.load_generation = gen
        worker.signals.result.connect(
            lambda p, img, g=gen, wk=worker: self._on_thumbnail_loaded(p, img, g, wk)
        )
        worker.signals.result.connect(lambda *_, g=gen: self._dispatch_fill(g))
        self._active_workers.add(worker)
        self.thread_pool.start(worker)

    # ------------------------------------------------------------------
    # In-database flag (used by scan-metadata styling)
    # ------------------------------------------------------------------

    def set_in_db(self, paths) -> None:
        """Set the full set of paths that exist in the database. Rows not in
        the set are unmarked; changed rows emit ``dataChanged`` so the view
        repaints their border."""
        new_set = set(paths)
        old_set = self._in_db
        if new_set == old_set:
            return
        self._in_db = new_set
        self._emit_data_changed_for_paths(new_set ^ old_set, self.InDbRole)

    def mark_in_db(self, path: str, in_db: bool) -> None:
        """Flip a single row's in-db flag (e.g. after an upsert/removal)."""
        if in_db:
            if path in self._in_db:
                return
            self._in_db.add(path)
        else:
            if path not in self._in_db:
                return
            self._in_db.discard(path)
        self._emit_data_changed_for_paths({path}, self.InDbRole)

    def is_in_db(self, path: str) -> bool:
        return path in self._in_db

    def set_selected(self, paths) -> None:
        """Set the full set of selected paths. Changed rows emit ``dataChanged``
        so the view repaints their selection border."""
        new_set = set(paths)
        old_set = self._selected
        if new_set == old_set:
            return
        self._selected = new_set
        self._emit_data_changed_for_paths(new_set ^ old_set, self.SelectedRole)

    def mark_selected(self, path: str, selected: bool) -> None:
        """Flip a single row's selected flag."""
        if selected:
            if path in self._selected:
                return
            self._selected.add(path)
        else:
            if path not in self._selected:
                return
            self._selected.discard(path)
        self._emit_data_changed_for_paths({path}, self.SelectedRole)

    def is_selected(self, path: str) -> bool:
        return path in self._selected

    def set_preview(self, paths) -> None:
        """Set the full set of paths currently open in a preview window.
        Changed rows emit ``dataChanged`` so the view repaints their border."""
        new_set = set(paths)
        old_set = self._preview
        if new_set == old_set:
            return
        self._preview = new_set
        self._emit_data_changed_for_paths(new_set ^ old_set, self.PreviewRole)

    def mark_preview(self, path: str, preview: bool) -> None:
        """Flip a single row's preview-open flag."""
        if preview:
            if path in self._preview:
                return
            self._preview.add(path)
        else:
            if path not in self._preview:
                return
            self._preview.discard(path)
        self._emit_data_changed_for_paths({path}, self.PreviewRole)

    def is_preview(self, path: str) -> bool:
        return path in self._preview

    def _emit_data_changed_for_paths(self, paths, role: int) -> None:
        for path in paths:
            row = self.row_for_path(path)
            if row >= 0:
                self.dataChanged.emit(
                    self.index(row, 0),
                    self.index(row, 0),
                    [role],
                )

    def set_overlay_metadata(
        self,
        path: str,
        *,
        rating: Optional[str] = None,
        resolution: Optional[tuple[int, int]] = None,
        file_format: Optional[str] = None,
        star_rating: Optional[float] = None,
        tag_count: Optional[int] = None,
    ) -> None:
        """Set or update custom thumbnail overlay metadata for *path*."""
        if rating is not None:
            self._ratings[path] = rating
        if resolution is not None:
            self._resolutions[path] = resolution
        if file_format is not None:
            self._formats[path] = file_format
        if star_rating is not None:
            self._star_ratings[path] = star_rating
        if tag_count is not None:
            self._tag_counts[path] = tag_count
        row = self.row_for_path(path)
        if row >= 0:
            self.dataChanged.emit(self.index(row, 0), self.index(row, 0))

    def clear_overlay_metadata(self) -> None:
        """Clear all stored overlay badges and metrics."""
        self._ratings.clear()
        self._resolutions.clear()
        self._formats.clear()
        self._star_ratings.clear()
        self._tag_counts.clear()

    def clear(self) -> None:
        self._selected.clear()
        self._preview.clear()
        self.clear_overlay_metadata()
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

    def rename_path(self, old_path: str, new_path: str) -> bool:
        """Rename an item path in the model and transfer cached data (§2.26)."""
        if old_path not in self._paths:
            return False
        idx = self._paths.index(old_path)
        self._paths[idx] = new_path
        pix = self._cache.pop(old_path, None)
        if pix is not None:
            self._cache[new_path] = pix
        for store in (self._ratings, self._resolutions, self._formats, self._star_ratings, self._tag_counts):
            if old_path in store:
                store[new_path] = store.pop(old_path)
        model_idx = self.index(idx, 0)
        self.dataChanged.emit(model_idx, model_idx)
        return True

    def set_thumbnail_size(self, size: int) -> None:
        """Change the served decoration size; cached QImages are rescaled on
        access, so zooming never reloads from disk. Emits ``layoutChanged``
        so the view re-lays-out with the new grid size."""
        size = max(32, size)
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
        """Stop and drain queued/in-flight loads before returning."""
        self._generation += 1
        self._cancel_workers()
        self._loading.clear()
        self._failed.clear()
        self._fill_queue.clear()

    def _cancel_workers(self) -> None:
        """Stop and drain work before a directory/model generation swap.

        Dropping Python references while an auto-deleting ``QRunnable`` is
        still emitting through its signal object leaves Qt and Shiboken racing
        ownership of the same connection graph. Directory replacement is rare,
        so a complete drain is preferable to allowing generations to overlap.
        """
        for worker in list(self._active_workers):
            stop = getattr(worker, "stop", None)
            if callable(stop):
                stop()
        self.thread_pool.clear()
        if self.thread_pool.activeThreadCount() > 0:
            self.thread_pool.waitForDone(-1)
        self._active_workers.clear()

    def has_pending_loads(self) -> bool:
        """Whether queued, running, or not-yet-delivered loads remain."""
        return bool(
            self._fill_queue
            or self._active_workers
            or self._loading
            or self.thread_pool.activeThreadCount()
        )

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
            name = os.path.basename(path)
            res = self._resolutions.get(path)
            res_str = f"{res[0]} × {res[1]}" if res else ""
            fmt = self._formats.get(path) or os.path.splitext(path)[1].upper().lstrip(".")
            star = self._star_ratings.get(path)
            rating = self._ratings.get(path)
            tags = self._tag_counts.get(path)

            details = []
            if res_str:
                details.append(f"Dimensions: {res_str}")
            if fmt:
                details.append(f"Format: {fmt}")
            if star:
                details.append(f"Rating: ★ {star}")
            if rating:
                details.append(f"Content: {str(rating).upper()}")
            if tags:
                details.append(f"Tags: {tags}")

            detail_lines = "\n".join(details)
            return f"{name}\n{detail_lines}" if details else name
        if role == self.PathRole:
            return path
        if role == self.InDbRole:
            return path in self._in_db
        if role == self.SelectedRole:
            return path in self._selected
        if role == self.PreviewRole:
            return path in self._preview
        if role == self.RatingRole:
            return self._ratings.get(path)
        if role == self.ResolutionRole:
            return self._resolutions.get(path)
        if role == self.FormatRole:
            return self._formats.get(path)
        if role == self.StarRatingRole:
            return self._star_ratings.get(path)
        if role == self.TagCountRole:
            return self._tag_counts.get(path)
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
            lambda p, img, g=gen, wk=worker: self._on_thumbnail_loaded(p, img, g, wk)
        )
        self._active_workers.add(worker)
        self.thread_pool.start(worker)

    def _on_thumbnail_loaded(self, path: str, image, generation: int, worker=None) -> None:
        # Queued (cross-thread) signal may arrive after the model's QObject
        # is torn down; guard first (same as the QLabel galleries).
        if not Shiboken.isValid(self):
            return
        # Drop the worker's strong ref first so stale deliveries (and the
        # failure path below) don't leak entries in _active_workers. The worker
        # is passed explicitly through the lambda closure (sender() is None for
        # a lambda-wrapped slot, so the QLabel-gallery sender() lookup can't be
        # reused here).
        if worker is not None:
            self._active_workers.discard(worker)
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
