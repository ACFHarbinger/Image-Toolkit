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
from typing import Dict, List, Optional

from PySide6.QtCore import QPoint, QRect, Qt, QThreadPool, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QWidget,
)

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
        self.thread_pool = QThreadPool.globalInstance()
        self._active_workers: set = set()
        # Generation counter: invalidates queued load-chunks after cancel/restart
        self._load_generation: int = 0

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

        # --- Open preview windows list ----------------------------------------
        self.open_preview_windows: List[QWidget] = []

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
        from gui.src.utils.thumbnail_size import save_thumbnail_size
        save_thumbnail_size(self.__class__.__name__, self.thumbnail_size)

    def _load_thumbnail_size(self, default: int = 180) -> int:
        from gui.src.utils.thumbnail_size import load_thumbnail_size
        return load_thumbnail_size(self.__class__.__name__, default)

    # =========================================================================
    # Recent directories / session persistence (GUI/UX §2.10, §2.5)
    # =========================================================================

    def _add_recent_dir(self, path: str, max_entries: int = 10) -> None:
        """Push *path* to the front of the per-class MRU directory list."""
        from gui.src.windows.settings.app_settings import AppSettings
        cn = self.__class__.__name__
        dirs: list = AppSettings.session(cn, "recent_dirs", []) or []
        if path in dirs:
            dirs.remove(path)
        dirs.insert(0, path)
        AppSettings.set_session(cn, "recent_dirs", dirs[:max_entries])

    def _get_recent_dirs(self) -> list:
        """Return the MRU directory list for this tab class."""
        main_win = self.window()
        if not main_win:
            for widget in QApplication.topLevelWidgets():
                if hasattr(widget, "cached_creds"):
                    main_win = widget
                    break
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
            if not prefs.get("restore_last_dir", True):
                return []
        from gui.src.windows.settings.app_settings import AppSettings
        return AppSettings.session(self.__class__.__name__, "recent_dirs", []) or []

    def _save_last_dir(self, path: str) -> None:
        main_win = self.window()
        if not main_win:
            for widget in QApplication.topLevelWidgets():
                if hasattr(widget, "cached_creds"):
                    main_win = widget
                    break
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
            if not prefs.get("restore_last_dir", True):
                return
        from gui.src.windows.settings.app_settings import AppSettings
        AppSettings.set_session(self.__class__.__name__, "last_dir", path)

    def _load_last_dir(self, default: str = "") -> str:
        main_win = self.window()
        if not main_win:
            for widget in QApplication.topLevelWidgets():
                if hasattr(widget, "cached_creds"):
                    main_win = widget
                    break
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
            if not prefs.get("restore_last_dir", True):
                return default
        from gui.src.windows.settings.app_settings import AppSettings
        return AppSettings.session(self.__class__.__name__, "last_dir", default)

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
        lbl.setStyleSheet(
            "color: #bbb; font-size: 8pt; padding: 0 2px; background: transparent;"
        )
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

    def common_reflow_layout(self, layout: Optional[QGridLayout], columns: int) -> None:
        """Re-organise *layout* to *columns* columns."""
        if not layout:
            return
        items = []
        placeholder = None
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                if isinstance(widget, QLabel) and getattr(widget, "is_placeholder", False):
                    placeholder = widget
                else:
                    items.append(widget)
        if placeholder:
            layout.addWidget(placeholder, 0, 0, 1, columns, Qt.AlignmentFlag.AlignCenter)
        else:
            for i, widget in enumerate(items):
                row = i // columns
                col = i % columns
                layout.addWidget(widget, row, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

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

    # =========================================================================
    # Chunked sequential load scheduling (progressive gallery fill)
    # =========================================================================

    def common_start_chunked_load(
        self,
        paths: list,
        worker_factory,
        per_result_slot=None,
        batch_slot=None,
        chunk_size: int = 8,
        max_in_flight: int = 2,
    ) -> None:
        """Dispatch *paths* to workers in sequential chunks.

        Previously every chunk-worker was queued on the thread pool at once;
        with the native loader's OpenMP loop competing for the same cores,
        all chunks progressed in parallel and completed clustered at the end,
        so the whole page appeared at once. Dispatching at most
        *max_in_flight* chunks and starting the next only when one finishes
        makes thumbnails appear top-to-bottom as they load, at the same (or
        better) total throughput.

        Cancellation: `cancel_loading` implementations bump
        ``self._load_generation``; queued continuations from an older
        generation are dropped.
        """
        if not paths:
            return
        gen = self._load_generation
        chunks = deque(
            paths[i : i + chunk_size] for i in range(0, len(paths), chunk_size)
        )

        def start_next(*_args):
            if gen != self._load_generation or not chunks:
                return
            chunk = chunks.popleft()
            worker = worker_factory(chunk)
            if per_result_slot is not None:
                worker.signals.result.connect(per_result_slot)
            if batch_slot is not None:
                worker.signals.batch_result.connect(batch_slot)
            # Chain: when this chunk finishes, dispatch the next one
            worker.signals.batch_result.connect(start_next)
            self._active_workers.add(worker)
            self.thread_pool.start(worker)

        for _ in range(min(max_in_flight, len(chunks))):
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
        lbl.setStyleSheet("color: #b9bbbe; padding: 20px; font-style: italic;")
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
        search_input.setStyleSheet(
            """
            QLineEdit {
                padding: 5px;
                border-radius: 4px;
                border: 1px solid #4f545c;
                background-color: #202225;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid #5865f2;
            }
            """
        )
        return search_input

    # =========================================================================
    # Search filter
    # =========================================================================

    def common_filter_string_list(self, full_list: list, query: str) -> list:
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
