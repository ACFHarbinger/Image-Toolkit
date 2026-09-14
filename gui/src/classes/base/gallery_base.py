"""
gui/src/classes/gallery_base.py
================================
Shared base class for all gallery tabs (A.16).

``AbstractGalleryBase`` extracts the shared ``__init__`` state and helper methods
that were previously duplicated across ``AbstractClassTwoGalleries`` and
``AbstractClassSingleGallery``, and converts the metaclass-injected ``common_*``
functions into normal inherited methods.

Class hierarchy after this refactor::

    QWidget
    └── AbstractGalleryBase  (metaclass=MetaAbstractClassGallery)
        ├── AbstractClassTwoGalleries   — found + selected panels
        └── AbstractClassSingleGallery  — single gallery panel
"""

from __future__ import annotations

import math
import os
import re as _re
from abc import abstractmethod
from collections import deque
from dataclasses import fields as _dc_fields
from typing import Dict, List, Optional

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSlider,
    QWidget,
)

from gui.src.components.gallery.presentation_mode import (
    GalleryOverlayConfig,
    GalleryPresentationMode,
)
from gui.src.constants.ui import RATING_COLORS
from gui.src.theming.theme_api import color, qss
from gui.src.thumbnails import DefaultThumbnailScheduler, ThumbnailScheduler, order_visible_first

from ..meta.meta_abstract_class_gallery import MetaAbstractClassGallery

# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _make_vline() -> QFrame:
    """Thin vertical separator widget for pagination bars."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    line.setFixedWidth(2)
    return line


# ---------------------------------------------------------------------------
# AbstractGalleryBase
# ---------------------------------------------------------------------------

class AbstractGalleryBase(QWidget, metaclass=MetaAbstractClassGallery):
    """Shared base class for gallery tabs.

    Provides:
    * Shared ``__init__`` state (thumbnail sizing, threading, resize timer,
      sort state, dir-history stacks).
    * Nine ``common_*`` UI helpers as real inherited methods.
    * Settings-backed helpers: ``_add_recent_dir``, ``_load_last_dir``, etc.
    * Sort helpers: ``_sort_key_fn``, ``_apply_sort``, ``_SORT_KEY_MAP``.
    * Abstract interface: ``get_default_config``, ``set_config``,
      ``_on_layout_change``.
    """

    def __init__(self) -> None:
        super().__init__()

        # --- UI configuration --------------------------------------------------
        self.thumbnail_size: int = self._load_thumbnail_size(default=180)
        self.padding_width: int = 10
        self.approx_item_width: int = (
            self.thumbnail_size + self.padding_width + 20
        )

        # --- Threading ---------------------------------------------------------
        # Dedicated pool per gallery instance, NOT QThreadPool.globalInstance().
        # The global pool is shared app-wide: a cancel_loading()'s
        # thread_pool.waitForDone(-1) on it (e.g. the wallpaper startup-restore
        # path) blocks the main thread until EVERY tab's pooled worker
        # finishes -- including another tab's long-running ffmpeg thumbnail
        # batch (subprocess.communicate waiting on the ffmpeg pipe). That
        # freezes startup and then aborts the process (issue #81 family;
        # observed live as "Fatal Python error: Aborted" with the main thread
        # in thread_pool.waitForDone and a pooled worker inside
        # subprocess._communicate). A per-instance pool makes cancel_loading()
        # drain only THIS gallery's own workers. Capped so N galleries never
        # spawn N * cpu_count threads.
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(max(2, min(8, os.cpu_count() or 4)))
        self._active_workers: set = set()
        # Keep queues isolated by gallery panel.  Found and selected panels can
        # load concurrently and need different worker factories/result slots;
        # sharing one FIFO lets either continuation drain the other's paths.
        # 64 = 4 in-flight chunks × 16 paths, matching the defaults below.
        self._thumbnail_scheduler: ThumbnailScheduler = DefaultThumbnailScheduler(
            max_in_flight=64
        )
        self._thumbnail_schedulers: dict[str, ThumbnailScheduler] = {
            "default": self._thumbnail_scheduler,
        }

        # --- Resize debouncing ------------------------------------------------
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_layout_change)

        # --- Ctrl+scroll zoom wired flag --------------------------------------
        self._scroll_zoom_connected: bool = False

        # --- Sort state -------------------------------------------------------
        self._sort_key: str = "name"
        self._sort_reverse: bool = False

        # --- Directory navigation history (GUI/UX §2.21A) --------------------
        self._dir_back_stack: deque = deque(maxlen=20)
        self._dir_forward_stack: deque = deque(maxlen=20)

        # --- Recent-directories MRU limit (GUI/UX §2.9G) ----------------------
        # Overwritten from the vault-stored "recent_dirs_count" preference by
        # main_window.py::_apply_startup_preferences(); defaults to 10 for
        # backward compatibility with existing saved configs.
        self.recent_dirs_limit: int = 10

        # --- Open preview windows list ----------------------------------------
        self.open_preview_windows: List[QWidget] = []

        # --- Presentation modes & overlay badges (§2.40 / #508) ---------------
        # Uniform grid is the historical behavior and stays the default; the
        # other modes only activate through set_presentation_mode().
        self._presentation_mode: GalleryPresentationMode = GalleryPresentationMode.UNIFORM_GRID
        self._overlay_config: GalleryOverlayConfig = GalleryOverlayConfig()
        self._card_overlay_metadata: Dict[str, dict] = {}
        self._presentation_menu_viewports: set = set()
        self._masonry_state: Dict[QGridLayout, dict] = {}
        self._masonry_reflow_timer = QTimer(self)
        self._masonry_reflow_timer.setSingleShot(True)
        self._masonry_reflow_timer.setInterval(120)
        self._masonry_reflow_timer.timeout.connect(self._on_layout_change)
        self._load_presentation_prefs()

    @property
    def _load_generation(self) -> int:
        """Live scheduler generation. Stale chunk deliveries compare against this."""
        return self._thumbnail_scheduler.generation

    def _thumbnail_scheduler_for(self, stream_key: str) -> ThumbnailScheduler:
        """Return the scheduler owned by one independent gallery load stream."""
        scheduler = self._thumbnail_schedulers.get(stream_key)
        if scheduler is not None:
            return scheduler

        scheduler = DefaultThumbnailScheduler(max_in_flight=64)
        # A stream can be created after a cancellation; align it with the
        # generation used by single-image/video workers and result handlers.
        for _ in range(self._thumbnail_scheduler.generation):
            scheduler.cancel()
        self._thumbnail_schedulers[stream_key] = scheduler
        return scheduler

    def cancel_thumbnail_schedulers(self) -> None:
        """Invalidate queued continuations for every active gallery stream."""
        for scheduler in self._thumbnail_schedulers.values():
            scheduler.cancel()

    # =========================================================================
    # Abstract interface
    # =========================================================================

    @abstractmethod
    def get_default_config(self) -> dict:
        """Return the default tab configuration dict."""

    @abstractmethod
    def set_config(self, config: dict) -> None:
        """Populate input fields from a saved configuration dict."""

    @abstractmethod
    def _on_layout_change(self) -> None:
        """Recalculate column count and reflow the gallery after a resize."""

    # =========================================================================
    # Sort helpers (GUI/UX §2.13A)
    # =========================================================================

    _SORT_KEY_MAP: Dict[str, str] = {
        "Name": "name",
        "Date Modified": "mtime",
        "File Size": "size",
        "Extension": "ext",
    }

    def _sort_key_fn(self, path: str):
        from ...utils.sort_utils import natural_sort_key
        key = self._sort_key
        if key == "mtime":
            try:
                return os.path.getmtime(path)
            except OSError:
                return 0.0
        if key == "size":
            try:
                return os.path.getsize(path)
            except OSError:
                return 0
        if key == "ext":
            return os.path.splitext(path)[1].lower()
        return natural_sort_key(path)

    def _apply_sort(self, paths: list) -> list:
        return sorted(paths, key=self._sort_key_fn, reverse=self._sort_reverse)

    # =========================================================================
    # Thumbnail size persistence (GUI/UX §4.11)
    # =========================================================================

    def _save_thumbnail_size(self) -> None:
        from gui.src.windows.settings.thumbnail_size import save_thumbnail_size
        save_thumbnail_size(self.__class__.__name__, self.thumbnail_size)

    def _load_thumbnail_size(self, default: int = 180) -> int:
        from gui.src.windows.settings.thumbnail_size import load_thumbnail_size
        return load_thumbnail_size(self.__class__.__name__, default)

    # =========================================================================
    # Recent directories / session persistence (GUI/UX §2.10, §2.5)
    # =========================================================================

    def _add_recent_dir(self, path: str, max_entries: Optional[int] = None) -> None:
        """Push *path* to the front of the per-class MRU directory list.

        ``max_entries`` defaults to ``self.recent_dirs_limit`` (populated from
        the "recent_dirs_count" preference by
        ``main_window.py::_apply_startup_preferences()``, itself defaulting to
        10) so callers don't need to plumb the preference through manually.
        """
        from gui.src.windows.settings.app_settings import AppSettings
        if max_entries is None:
            max_entries = getattr(self, "recent_dirs_limit", 10)
        cn = self.__class__.__name__
        dirs = AppSettings.session(cn, "recent_dirs", []) or []
        # QSettings round-trips a single-element list as a bare string on
        # some backends (a well-known QVariant quirk) -- normalize so a
        # second browse to any directory after the list has shrunk to one
        # entry doesn't crash with "'str' object has no attribute 'remove'".
        if isinstance(dirs, str):
            dirs = [dirs]
        dirs = list(dirs)
        if path in dirs:
            dirs.remove(path)
        dirs.insert(0, path)
        AppSettings.set_session(cn, "recent_dirs", dirs[:max_entries])

    def _get_recent_dirs(self) -> list:
        """Return the MRU directory list for this tab class."""
        main_win = self.window()
        if not main_win:
            from gui.src.windows.window_manager import WindowManager

            main_win = WindowManager.instance().main_window()
            if main_win is None:
                main_win = WindowManager.instance().find(lambda w: hasattr(w, "cached_creds"))
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
            if not prefs.get("restore_last_dir", True):
                return []
        from gui.src.windows.settings.app_settings import AppSettings
        dirs = AppSettings.session(self.__class__.__name__, "recent_dirs", []) or []
        # Same QSettings single-element round-trip quirk as _add_recent_dir.
        if isinstance(dirs, str):
            dirs = [dirs]
        return list(dirs)

    def _save_last_dir(self, path: str, main_win = None) -> None:
        if path and "Downloads/data" in path:
            path = path.replace("Downloads/data", "Downloads/Data")
        if not main_win:
            main_win = self.window()
        if not main_win:
            from gui.src.windows.window_manager import WindowManager

            main_win = WindowManager.instance().main_window()
            if main_win is None:
                main_win = WindowManager.instance().find(lambda w: hasattr(w, "cached_creds"))
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
            if not prefs.get("restore_last_dir", True):
                return
        from gui.src.windows.settings.app_settings import AppSettings
        AppSettings.set_session(self.__class__.__name__, "last_dir", path)

    def _load_last_dir(self, default: str = "", main_win = None) -> str:
        if not main_win:
            main_win = self.window()
        if not main_win:
            from gui.src.windows.window_manager import WindowManager

            main_win = WindowManager.instance().main_window()
            if main_win is None:
                main_win = WindowManager.instance().find(lambda w: hasattr(w, "cached_creds"))
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
            default_dir = prefs.get("default_open_dir", "").strip()
            if default_dir:
                default = default_dir
            if not prefs.get("restore_last_dir", True):
                # Auto-correct any lowercase Downloads/data path to Downloads/Data
                if default and "Downloads/data" in default:
                    default = default.replace("Downloads/data", "Downloads/Data")
                return default
        # Auto-correct any lowercase Downloads/data path to Downloads/Data
        if default and "Downloads/data" in default:
            default = default.replace("Downloads/data", "Downloads/Data")
        from gui.src.windows.settings.app_settings import AppSettings
        val = AppSettings.session(self.__class__.__name__, "last_dir", default)
        if val and "Downloads/data" in val:
            val = val.replace("Downloads/data", "Downloads/Data")
        return val

    # =========================================================================
    # Status bar helper (GUI/UX §2.10C)
    # =========================================================================

    def _show_status(self, message: str, timeout_ms: int = 3000) -> None:
        """Post *message* to the main-window status bar."""
        from gui.src.windows.main.main_window import show_main_status
        show_main_status(message, timeout_ms)

    # =========================================================================
    # Filename label below thumbnail (GUI/UX §2.14A)
    # =========================================================================

    def _add_filename_label(self, card: QWidget, path: str) -> None:
        """Append a truncated filename QLabel at the bottom of *card*'s layout."""
        layout = card.layout()
        if layout is None:
            return
        name = os.path.basename(path)
        lbl = QLabel()
        lbl.setObjectName("thumb_filename_lbl")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        max_w = self.thumbnail_size + 10
        fm = lbl.fontMetrics()
        label_h = fm.height() + 4
        elided = fm.elidedText(name, Qt.TextElideMode.ElideMiddle, max_w)
        lbl.setText(elided)
        lbl.setToolTip(name)
        lbl.setMaximumWidth(max_w)
        lbl.setFixedHeight(label_h)
        lbl.setStyleSheet(qss("gallery_thumb_filename"))
        layout.addWidget(lbl)
        # If the card has an explicitly constrained height (setFixedSize), expand
        # it to accommodate the label. Cards without a fixed height are unaffected
        # because Qt's QWIDGETSIZE_MAX (16777215) fails the upper bound check.
        fixed_h = card.maximumHeight()
        if 0 < fixed_h < 16777215:
            card.setFixedHeight(fixed_h + label_h)

    # =========================================================================
    # Static utility
    # =========================================================================

    @staticmethod
    def join_list_str(text: str) -> List[str]:
        """Convert a comma/space-separated string to a list, stripping leading dots."""
        return [
            item.strip().lstrip(".")
            for item in text.replace(",", " ").split()
            if item.strip()
        ]

    # =========================================================================
    # Pagination UI builder (§3.9 + §4.11)
    # =========================================================================

    def common_create_pagination_ui(self):
        """Build the standardised pagination bar widget.

        Returns
        -------
        container : QWidget
        controls : dict
            Keys: ``combo``, ``btn_prev``, ``btn_page``, ``btn_next``,
            ``item_range_lbl``, ``thumb_slider``, ``thumb_size_lbl``,
            ``sort_combo``, ``sort_dir_btn``.
        """
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        lbl = QLabel("Images per page:")
        combo = QComboBox()
        combo.addItems(["20", "50", "100", "150", "250", "500", "1000", "All"])
        combo.setCurrentText("150")
        combo.setAccessibleName("Images per page")

        sort_lbl = QLabel("Sort:")
        sort_combo = QComboBox()
        sort_combo.addItems(["Name", "Date Modified", "File Size", "Extension"])
        sort_combo.setFixedWidth(120)
        sort_combo.setAccessibleName("Sort by")
        sort_dir_btn = QPushButton("↑")
        sort_dir_btn.setFixedWidth(28)
        sort_dir_btn.setToolTip("Toggle sort direction")
        sort_dir_btn.setAccessibleName("Toggle sort direction")

        btn_prev = QPushButton("< Prev")
        btn_prev.setAccessibleName("Previous page")
        btn_page = QPushButton("Page 1 / 1")
        btn_page.setFixedWidth(120)
        btn_page.setAccessibleName("Current page")
        btn_next = QPushButton("Next >")
        btn_next.setAccessibleName("Next page")

        item_range_lbl = QLabel("0 images")
        item_range_lbl.setMinimumWidth(120)
        item_range_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        item_range_lbl.setAccessibleName("Item range")

        thumb_slider = QSlider(Qt.Orientation.Horizontal)
        thumb_slider.setRange(64, 512)
        thumb_slider.setSingleStep(16)
        thumb_slider.setPageStep(32)
        thumb_slider.setValue(180)
        thumb_slider.setFixedWidth(110)
        thumb_slider.setToolTip("Thumbnail size (64–512 px)")
        thumb_slider.setAccessibleName("Thumbnail size")
        thumb_slider.setAccessibleDescription(
            "Drag to resize gallery thumbnails between 64 and 512 pixels"
        )

        thumb_size_lbl = QLabel("180 px")
        thumb_size_lbl.setMinimumWidth(44)
        thumb_size_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(lbl)
        layout.addWidget(combo)
        layout.addWidget(sort_lbl)
        layout.addWidget(sort_combo)
        layout.addWidget(sort_dir_btn)
        layout.addStretch()
        layout.addWidget(item_range_lbl)
        layout.addWidget(_make_vline())
        layout.addWidget(btn_prev)
        layout.addWidget(btn_page)
        layout.addWidget(btn_next)
        layout.addWidget(_make_vline())
        layout.addWidget(QLabel("⊞"))
        layout.addWidget(thumb_slider)
        layout.addWidget(thumb_size_lbl)

        controls = {
            "combo": combo,
            "btn_prev": btn_prev,
            "btn_page": btn_page,
            "btn_next": btn_next,
            "item_range_lbl": item_range_lbl,
            "thumb_slider": thumb_slider,
            "thumb_size_lbl": thumb_size_lbl,
            "sort_combo": sort_combo,
            "sort_dir_btn": sort_dir_btn,
        }
        return container, controls

    # =========================================================================
    # Pagination state updater
    # =========================================================================

    def common_update_pagination_state(
        self, total_items: int, page_size: int, current_page: int, controls_dict: dict
    ):
        """Update enabled state and text of pagination controls.

        Returns
        -------
        corrected_page : int
        total_pages : int
        """
        btn_page = controls_dict["btn_page"]
        btn_prev = controls_dict["btn_prev"]
        btn_next = controls_dict["btn_next"]

        if total_items == 0:
            btn_page.setText("Page 0 / 0")
            btn_page.setEnabled(False)
            btn_prev.setEnabled(False)
            btn_next.setEnabled(False)
            return 0, 0

        total_pages = math.ceil(total_items / page_size)
        if current_page >= total_pages:
            current_page = max(0, total_pages - 1)

        btn_page.setText(f"Page {current_page + 1} / {total_pages}")
        btn_page.setEnabled(True)
        btn_prev.setEnabled(current_page > 0)
        btn_next.setEnabled(current_page < total_pages - 1)
        return current_page, total_pages

    # =========================================================================
    # Column calculation
    # =========================================================================

    def common_calculate_columns(self, scroll_area, approx_width: int) -> int:
        """Calculate how many columns fit in *scroll_area*."""
        if not scroll_area:
            return 1
        viewport = scroll_area.viewport()
        width = viewport.width()
        if width <= 0:
            width = scroll_area.width()
        if width <= 0:
            return 4
        return max(1, width // approx_width)

    # =========================================================================
    # Layout reflow
    # =========================================================================

    @staticmethod
    def _card_height_hint(widget: QWidget) -> int:
        """Effective card height for packing. sizeHint() reports the layout's
        natural hint and ignores setFixedSize(), so prefer the minimum height
        (which setFixedSize sets) and only then fall back to sizeHint()."""
        h = widget.minimumHeight()
        if h <= 0:
            h = widget.sizeHint().height()
        return max(1, h)

    def common_place_card(
        self, layout: Optional[QGridLayout], card: QWidget, index: int, columns: int
    ) -> None:
        """Place one freshly-created card according to the active presentation
        mode. Populate loops call this instead of open-coding row/col math so
        every mode shares one placement path."""
        if not layout:
            return
        self._ensure_presentation_menu(layout)
        mode = self._presentation_mode
        if mode == GalleryPresentationMode.MASONRY:
            state = self._masonry_state.setdefault(
                layout, {"heights": [0] * max(1, columns), "next_row": 0}
            )
            if len(state["heights"]) != max(1, columns):
                # Column count changed since the last pack (e.g. an empty
                # reflow seeded a different width) -- reseed.
                state["heights"] = [0] * max(1, columns)
                state["next_row"] = layout.count()
            heights = state["heights"]
            col = heights.index(min(heights))
            row = state["next_row"]
            layout.addWidget(card, row, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            heights[col] += self._card_height_hint(card)
            state["next_row"] = row + 1
        elif mode == GalleryPresentationMode.COMPACT_LIST:
            layout.addWidget(card, index, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        else:
            layout.addWidget(
                card,
                index // columns,
                index % columns,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            )

    def common_reflow_layout(self, layout: Optional[QGridLayout], columns: int) -> None:
        """Re-organise *layout* to *columns* columns, honoring the active
        presentation mode (§2.40 / #508)."""
        if not layout:
            return
        self._ensure_presentation_menu(layout)
        items, placeholder = self._extract_layout_cards(layout)
        if placeholder:
            layout.addWidget(placeholder, 0, 0, 1, columns, Qt.AlignmentFlag.AlignCenter)
            return
        mode = self._presentation_mode
        if mode == GalleryPresentationMode.MASONRY:
            self._reflow_masonry(layout, items, columns)
        elif mode == GalleryPresentationMode.COMPACT_LIST:
            for i, widget in enumerate(items):
                layout.addWidget(widget, i, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        else:
            for i, widget in enumerate(items):
                row = i // columns
                col = i % columns
                layout.addWidget(widget, row, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    @staticmethod
    def _extract_layout_cards(layout: QGridLayout) -> tuple[list, Optional[QLabel]]:
        items: list = []
        placeholder = None
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                if isinstance(widget, QLabel) and getattr(widget, "is_placeholder", False):
                    placeholder = widget
                else:
                    items.append(widget)
        return items, placeholder

    def _reflow_masonry(self, layout: QGridLayout, items: list, columns: int) -> None:
        # QGridLayout sizes each row to its tallest cell, so true masonry
        # needs every card on its OWN row index: each row then holds exactly
        # one widget and takes that widget's height. Columns accumulate
        # independent heights; each card drops onto the shortest column.
        columns = max(1, columns)
        heights = [0] * columns
        for widget in items:
            col = heights.index(min(heights))
            row = layout.count()
            layout.addWidget(widget, row, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            heights[col] += self._card_height_hint(widget)
        self._masonry_state[layout] = {"heights": heights, "next_row": layout.count()}

    # =========================================================================
    # Presentation modes & overlay badges (§2.40 / #508)
    # =========================================================================

    _OVERLAY_FIELDS = tuple(f.name for f in _dc_fields(GalleryOverlayConfig))
    _COMPACT_THUMB = 48

    @property
    def presentation_mode(self) -> GalleryPresentationMode:
        return self._presentation_mode

    def set_presentation_mode(self, mode: GalleryPresentationMode) -> None:
        mode = GalleryPresentationMode(mode)
        if mode == self._presentation_mode:
            return
        self._presentation_mode = mode
        self._save_presentation_prefs()
        for card in self._iter_gallery_cards():
            if mode == GalleryPresentationMode.COMPACT_LIST:
                self._apply_compact_geometry(card)
            elif mode == GalleryPresentationMode.MASONRY:
                self._apply_masonry_geometry(card)
            else:
                self._restore_uniform_geometry(card)
        self._masonry_state.clear()
        self._on_layout_change()
        self._reflow_presentation_layouts()

    def _reflow_presentation_layouts(self) -> None:
        """Reflow existing cards when a mode changes without a resize.

        The regular layout-change handlers only reflow after a column-count
        change. A presentation-mode switch needs a reflow even at the same
        viewport width.
        """
        for layout_attr, columns_attr in (
            ("gallery_layout", "_current_cols"),
            ("found_gallery_layout", "_current_found_cols"),
            ("selected_gallery_layout", "_current_selected_cols"),
        ):
            layout = getattr(self, layout_attr, None)
            if layout is not None:
                self.common_reflow_layout(layout, max(1, getattr(self, columns_attr, 1)))

    def set_overlay_config(self, config: GalleryOverlayConfig) -> None:
        self._overlay_config = config
        self._save_presentation_prefs()
        for card in self._iter_gallery_cards():
            path = (
                card.property("gallery_path")
                or getattr(card, "path", "")
                or getattr(card, "file_path", "")
                or ""
            )
            self._apply_card_overlays(card, path)

    def set_overlay_metadata(self, path: str, **fields) -> None:
        """Record overlay metadata for one card (mirrors the
        ``VirtualGalleryModel.set_overlay_metadata`` surface)."""
        self._card_overlay_metadata[path] = dict(fields)
        card = self._card_for_path(path)
        if card is not None:
            self._apply_card_overlays(card, path)

    def clear_overlay_metadata(self) -> None:
        self._card_overlay_metadata.clear()
        for card in self._iter_gallery_cards():
            self._remove_badge_strip(card)

    def _card_for_path(self, path: str) -> Optional[QWidget]:
        for attr in ("path_to_card_widget", "path_to_label_map", "selected_card_map"):
            mapping = getattr(self, attr, None)
            if mapping and path in mapping:
                try:
                    return mapping[path]
                except RuntimeError:
                    return None
        return None

    def _iter_gallery_cards(self):
        seen: set = set()
        for attr in ("path_to_card_widget", "path_to_label_map", "selected_card_map"):
            mapping = getattr(self, attr, None)
            if not mapping:
                continue
            for card in list(mapping.values()):
                try:
                    if id(card) in seen:
                        continue
                    seen.add(id(card))
                    yield card
                except RuntimeError:
                    continue

    def _load_presentation_prefs(self) -> None:
        try:
            from gui.src.windows.settings.app_settings import AppSettings

            cn = self.__class__.__name__
            mode = AppSettings.session(cn, "presentation_mode", "") or ""
            if mode:
                self._presentation_mode = GalleryPresentationMode(mode)
            stored = AppSettings.session(cn, "gallery_overlay_config", {}) or {}
            if isinstance(stored, dict):
                self._overlay_config = GalleryOverlayConfig(
                    **{k: bool(v) for k, v in stored.items() if k in self._OVERLAY_FIELDS}
                )
        except Exception:
            self._presentation_mode = GalleryPresentationMode.UNIFORM_GRID
            self._overlay_config = GalleryOverlayConfig()

    def _save_presentation_prefs(self) -> None:
        try:
            from gui.src.windows.settings.app_settings import AppSettings

            cn = self.__class__.__name__
            AppSettings.set_session(cn, "presentation_mode", self._presentation_mode.value)
            AppSettings.set_session(
                cn,
                "gallery_overlay_config",
                {f: bool(getattr(self._overlay_config, f)) for f in self._OVERLAY_FIELDS},
            )
        except Exception:
            pass

    # --- overlay badges ----------------------------------------------------

    def _apply_card_overlays(self, card: QWidget, path: str) -> None:
        """(Re)build the badge strip on one card from recorded metadata and
        the current ``GalleryOverlayConfig``."""
        self._remove_badge_strip(card)
        if not path:
            return
        cfg = self._overlay_config
        md = self._card_overlay_metadata.get(path) or {}
        chips: list[tuple[str, str]] = []  # (text, badge_bg) — bg "" = neutral
        if cfg.show_rating and md.get("rating"):
            letter = str(md["rating"]).upper()[:1]
            chips.append((letter, RATING_COLORS.get(str(md["rating"]).lower()[:1], color("accent"))))
        if cfg.show_resolution:
            res = md.get("resolution")
            if isinstance(res, (tuple, list)) and len(res) == 2:
                chips.append((f"{res[0]}×{res[1]}", ""))
        if cfg.show_format and md.get("file_format"):
            chips.append((str(md["file_format"]).upper(), ""))
        if cfg.show_star_rating and md.get("star_rating"):
            chips.append((f"★ {float(md['star_rating']):.1f}", ""))
        if cfg.show_tag_count and md.get("tag_count"):
            chips.append((f"🏷 {md['tag_count']}", ""))
        if not chips:
            return
        strip = QWidget(card)
        strip.setObjectName("gallery_card_badge_strip")
        row = QHBoxLayout(strip)
        row.setContentsMargins(2, 1, 2, 1)
        row.setSpacing(3)
        for text, bg in chips:
            badge = QLabel(text, strip)
            badge.setObjectName("gallery_card_badge")
            if bg:
                badge.setStyleSheet(qss("gallery_card_badge", BADGE_BG=bg, BADGE_TEXT=color("text")))
            else:
                badge.setStyleSheet(qss("gallery_card_badge"))
            row.addWidget(badge)
        row.addStretch(1)
        layout = card.layout()
        if layout is not None:
            layout.addWidget(strip)

    @staticmethod
    def _remove_badge_strip(card: QWidget) -> None:
        try:
            strip = card.findChild(QWidget, "gallery_card_badge_strip")
        except RuntimeError:
            return
        if strip is not None:
            strip.setParent(None)
            strip.deleteLater()

    # --- per-mode card geometry ---------------------------------------------

    @staticmethod
    def _card_image_label(card: QWidget) -> Optional[QLabel]:
        if isinstance(card, QLabel):
            return card
        try:
            for label in card.findChildren(QLabel):
                if label.objectName() in ("thumb_filename_lbl", "gallery_card_badge"):
                    continue
                return label
        except RuntimeError:
            return None
        return None

    def _remember_uniform_geometry(self, card: QWidget, label: QLabel) -> None:
        if card.property("gallery_base_orig_geometry") is None:
            card_h = card.minimumHeight()
            if card_h <= 0:
                card_h = card.sizeHint().height()
            card.setProperty(
                "gallery_base_orig_geometry",
                (max(1, card_h), label.width(), label.height()),
            )

    def _mutate_card_geometry(self, card: QWidget, *, thumb: Optional[int] = None, label_height: Optional[int] = None) -> None:
        label = self._card_image_label(card)
        if label is None:
            return
        self._remember_uniform_geometry(card, label)
        w = thumb if thumb is not None else label.width()
        h = label_height if label_height is not None else (thumb if thumb is not None else label.height())
        label.setFixedSize(w, h)
        orig_card_h, orig_label_w, orig_label_h = card.property("gallery_base_orig_geometry")
        # Container height follows the label: original container height minus
        # the original (square) label height, plus the new label height --
        # absorbs the filename label and badge strip when present.
        card.setMinimumHeight(0)
        card.setMaximumHeight(orig_card_h - orig_label_h + h)

    def _apply_compact_geometry(self, card: QWidget) -> None:
        self._mutate_card_geometry(card, thumb=self._COMPACT_THUMB)

    def _apply_masonry_geometry(self, card: QWidget) -> None:
        label = self._card_image_label(card)
        if label is None or not label.width():
            return
        pm = label.pixmap()
        if pm is None or pm.isNull() or pm.width() <= 0 or pm.height() <= 0:
            return
        thumb = self.thumbnail_size
        lo, hi = max(40, thumb // 2), thumb * 2
        target = int(label.width() * pm.height() / pm.width())
        self._mutate_card_geometry(card, label_height=int(min(max(target, lo), hi)))

    def _restore_uniform_geometry(self, card: QWidget) -> None:
        orig = card.property("gallery_base_orig_geometry")
        label = self._card_image_label(card)
        if orig is not None and label is not None:
            orig_card_h, orig_label_w, orig_label_h = orig
            label.setFixedSize(orig_label_w, orig_label_h)
            card.setMinimumHeight(orig_card_h)
            card.setMaximumHeight(orig_card_h)
        card.setProperty("gallery_base_orig_geometry", None)

    def notify_card_pixmap_loaded(self, widget: QWidget, pixmap) -> None:
        """Hook for subclass ``update_card_pixmap``: keep masonry card heights
        in sync with the just-arrived image aspect, then debounce a repack."""
        if self._presentation_mode != GalleryPresentationMode.MASONRY:
            return
        if pixmap is None or pixmap.isNull() or pixmap.width() <= 0 or pixmap.height() <= 0:
            return
        label = self._card_image_label(widget)
        if label is None or not label.width():
            return
        thumb = self.thumbnail_size
        lo, hi = max(40, thumb // 2), thumb * 2
        target = int(label.width() * pixmap.height() / pixmap.width())
        self._mutate_card_geometry(widget, label_height=int(min(max(target, lo), hi)))
        self._masonry_reflow_timer.start()

    # --- presentation menu (mirrors VirtualGalleryView) ----------------------

    def _ensure_presentation_menu(self, layout: QGridLayout) -> None:
        """Install the empty-space presentation menu on the scroll area that
        owns *layout*, once per viewport. Hooked from the shared reflow path
        so every gallery tab gets it without per-tab wiring."""
        content = layout.parentWidget()
        ancestor = content.parentWidget() if content is not None else None
        scroll = None
        while ancestor is not None:
            # setWidget() parents the content into the scroll area's
            # viewport, so the QScrollArea is one or two levels up.
            if isinstance(ancestor, QScrollArea):
                scroll = ancestor
                break
            ancestor = ancestor.parentWidget()
        if scroll is None:
            return
        viewport = scroll.viewport()
        if viewport in self._presentation_menu_viewports:
            return
        viewport.installEventFilter(self)
        self._presentation_menu_viewports.add(viewport)

    def eventFilter(self, obj, event) -> bool:  # noqa: C901
        if obj in self._presentation_menu_viewports and event.type() == QEvent.Type.ContextMenu:
            child = obj.childAt(event.pos())
            ancestor = child
            while ancestor is not None and ancestor is not obj:
                if ancestor.property("gallery_path"):
                    return False  # card right-click: existing handlers own it
                ancestor = ancestor.parentWidget()
            self._build_presentation_menu().exec(obj.mapToGlobal(event.pos()))
            return True
        return False

    def _build_presentation_menu(self) -> QMenu:
        """Build (but don't show) the mode/overlay menu -- kept action-for-action
        parallel with ``VirtualGalleryView._build_presentation_menu`` so both
        gallery kinds expose the same surface."""
        menu = QMenu(self)

        mode_menu = menu.addMenu("Presentation Mode")
        mode_group = QActionGroup(mode_menu)
        mode_group.setExclusive(True)
        for mode, label in (
            (GalleryPresentationMode.UNIFORM_GRID, "Uniform Grid"),
            (GalleryPresentationMode.MASONRY, "Masonry"),
            (GalleryPresentationMode.COMPACT_LIST, "Compact List"),
        ):
            action = QAction(label, mode_menu, checkable=True)
            action.setChecked(mode == self._presentation_mode)
            action.triggered.connect(lambda _checked=False, m=mode: self.set_presentation_mode(m))
            mode_group.addAction(action)
            mode_menu.addAction(action)

        overlay_menu = menu.addMenu("Thumbnail Overlays")
        cfg = self._overlay_config
        for attr, label in (
            ("show_rating", "Rating Badge"),
            ("show_resolution", "Resolution"),
            ("show_format", "Format"),
            ("show_star_rating", "Star Rating"),
            ("show_tag_count", "Tag Count"),
        ):
            action = QAction(label, overlay_menu, checkable=True)
            action.setChecked(bool(getattr(cfg, attr)))
            action.toggled.connect(
                lambda checked, a=attr, c=cfg: (setattr(c, a, checked), self.set_overlay_config(c))
            )
            overlay_menu.addAction(action)
        return menu

    # =========================================================================
    # Viewport visibility check
    # =========================================================================

    def common_is_visible(self, widget: QWidget, viewport, visible_rect: QRect) -> bool:
        """Return True if *widget* intersects the visible viewport rectangle."""
        if not widget.isVisible():
            return False
        p = widget.mapTo(viewport, QPoint(0, 0))
        widget_rect = QRect(p, widget.size())
        return visible_rect.intersects(widget_rect)

    def _sort_paths_by_visibility(
        self,
        paths: list,
        scroll_area,
        path_to_widget: dict,
    ) -> list:
        """Reorder *paths* so those whose card widget is visible in the
        viewport's scroll area come first.  Non-visible paths follow in
        their original order.

        This is the core primitive for visible-first thumbnail dispatch:
        the batch loaders (``common_start_chunked_load``) process their
        input list sequentially, so placing visible paths at the front
        ensures the user sees thumbnails populate top-to-bottom while
        offscreen paths load later. Ordering itself is the shared
        ``order_visible_first`` helper (#526); widget-to-viewport mapping
        stays gallery-local.
        """
        if not paths or not scroll_area:
            return paths
        viewport = scroll_area.viewport()
        if viewport is None:
            return paths
        visible_rect = viewport.rect()

        visible = []
        for path in paths:
            card = path_to_widget.get(path)
            if card is not None and self.common_is_visible(card, viewport, visible_rect):
                visible.append(path)
        return order_visible_first(paths, visible=visible)

    # =========================================================================
    # Chunked sequential load scheduling (progressive gallery fill)
    # =========================================================================

    def common_start_chunked_load(
        self,
        paths: list,
        worker_factory,
        batch_slot=None,
        chunk_size: int = 16,
        max_in_flight: int = 4,
        stream_key: str = "default",
    ) -> None:
        """Dispatch *paths* to workers in sequential chunks.

        Previously every chunk-worker was queued on the thread pool at once;
        with the native loader's OpenMP loop competing for the same cores,
        all chunks progressed in parallel and completed clustered at the end,
        so the whole page appeared at once. Dispatching at most
        *max_in_flight* chunks and starting the next only when one finishes
        makes thumbnails appear top-to-bottom as they load, at the same (or
        better) total throughput.

        Only ``batch_result`` is connected (#444): the batch workers emit
        both ``result`` (per path) and ``batch_result`` (same list), and
        connecting both slots ran update_card_pixmap() twice per thumbnail
        on the GUI thread. The batch slot owns rendering, caching, and
        worker cleanup; the per-result slots remain wired only for the
        single-shot ImageLoaderWorker/VideoLoaderWorker paths.

        Each ``stream_key`` owns a queue, so concurrent found and selected
        panels cannot dispatch paths with each other's factory or result slot.
        ``cancel_loading`` invalidates every stream's queued continuations.
        """
        if not paths:
            return
        scheduler = self._thumbnail_scheduler_for(stream_key)
        gen = scheduler.generation
        scheduler.enqueue(paths)

        def start_next(*_args):
            if not scheduler.is_current(gen):
                return
            chunk: list = []
            for _ in range(chunk_size):
                path = scheduler.take_next()
                if path is None:
                    break
                chunk.append(path)
            if not chunk:
                return
            worker = worker_factory(chunk)
            # Tag with the generation active at dispatch time so the result
            # handler (batch_slot) can tell a stale delivery (this chunk's
            # own generation no longer current, e.g. the user switched
            # directories again while it was in flight) from a current one,
            # and skip touching any gallery widget for a stale result --
            # this chunk's own queued signal isn't cancelled by bumping
            # generation, only the not-yet-dispatched *next* chunk is.
            worker.load_generation = gen

            def on_batch(*args, _chunk=chunk, _gen=gen):
                for path in _chunk:
                    scheduler.complete(path, _gen)
                start_next()

            # Gui-thread marshalling, split across two connections because a
            # PySide6 functor connect has no context object (a context-less
            # functor runs in the emitting worker thread):
            #   * `batch_slot` mutates gallery widgets, so it is connected as
            #     a QObject slot, which PySide6 queues onto the GUI thread.
            #   * `on_batch` (scheduler complete + next-chunk chain) is
            #     thread-safe (scheduler has its own lock) and stays on the
            #     worker thread, matching the pre-#543 chain.
            # Wrapping batch_slot inside the closure would run it off the GUI
            # thread — the QWidget-off-GUI-thread crash class this repo has
            # reverted for before (#543 review).
            if batch_slot is not None:
                worker.stream.batch_result.connect(batch_slot)
            worker.stream.batch_result.connect(on_batch)
            self._active_workers.add(worker)
            self.thread_pool.start(worker)

        for _ in range(max_in_flight):
            start_next()

    # =========================================================================
    # Paginated slice
    # =========================================================================

    def common_get_paginated_slice(self, full_list: list, page: int, page_size: int) -> list:
        """Return the subset of *full_list* for the given *page*."""
        start = page * page_size
        return full_list[start : start + page_size]

    # =========================================================================
    # Placeholder label
    # =========================================================================

    def common_show_placeholder(
        self, layout: Optional[QGridLayout], text: str, columns: int = 1
    ) -> None:
        """Clear *layout* and show a centred placeholder label."""
        if not layout:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater() # pyrefly: ignore [missing-attribute]
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(qss("gallery_placeholder"))
        lbl.is_placeholder = True # pyrefly: ignore [missing-attribute]
        layout.addWidget(lbl, 0, 0, 1, columns, Qt.AlignmentFlag.AlignCenter)

    # =========================================================================
    # Search input factory
    # =========================================================================

    def common_create_search_input(
        self, placeholder_text: str = 'Search… (-exclude "exact" a|b)'
    ) -> QLineEdit:
        """Create a styled search QLineEdit with hint text."""
        search_input = QLineEdit()
        search_input.setPlaceholderText(placeholder_text)
        search_input.setStyleSheet(qss("gallery_search_input"))
        return search_input

    # =========================================================================
    # Search filter
    # =========================================================================

    def common_filter_string_list(self, full_list: list, query: str) -> list:  # noqa: C901
        """Filter a list of strings with extended search operators (§2.13E).

        Supported syntax::

            -term        exclude paths containing "term"
            "phrase"     exact substring (case-insensitive)
            a|b          OR — matches paths containing "a" OR "b"
            plain text   standard case-insensitive substring match

        Tokens are AND-combined: all must match for a path to pass.
        """
        if not query:
            return full_list

        tokens = []
        remaining = query.strip()
        for phrase in _re.findall(r'"([^"]+)"', remaining):
            tokens.append(("phrase", phrase.lower()))
        remaining = _re.sub(r'"[^"]+"', "", remaining)
        for tok in remaining.split():
            if tok.startswith("-") and len(tok) > 1:
                tokens.append(("exclude", tok[1:].lower()))
            elif "|" in tok:
                tokens.append(("or", [p.lower() for p in tok.split("|") if p]))
            else:
                tokens.append(("include", tok.lower()))

        if not tokens:
            return full_list

        result = []
        for item in full_list:
            lower = item.lower()
            match = True
            for kind, val in tokens:
                if kind == "include":
                    if val not in lower:
                        match = False
                        break
                elif kind == "exclude":
                    if val in lower:
                        match = False
                        break
                elif kind == "phrase":
                    if val not in lower:
                        match = False
                        break
                elif kind == "or" and not any(v in lower for v in val):
                    match = False
                    break
            if match:
                result.append(item)
        return result
