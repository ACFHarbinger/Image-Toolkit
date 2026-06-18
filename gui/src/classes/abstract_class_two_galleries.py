import os
import math
from collections import deque

from abc import abstractmethod
from typing import List, Dict, Optional
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QMenu, QApplication, QFileDialog, QMessageBox, QInputDialog
from PySide6.QtCore import Qt, Slot, QThreadPool, QTimer, QEvent
from PySide6.QtGui import QPixmap, QImage, QAction
from backend.src.constants import (
    LOCAL_SOURCE_PATH,
    SUPPORTED_VIDEO_FORMATS,
    THUMBNAIL_CACHE_DIR,
)
from .meta_abstract_class_gallery import MetaAbstractClassGallery
from ..utils.lru_image_cache import LRUImageCache
from ..components import MarqueeScrollArea, ClickableLabel
from ..helpers import (
    ImageLoaderWorker,
    BatchImageLoaderWorker,
    VideoLoaderWorker,
    BatchVideoLoaderWorker,
)
from ..utils.sort_utils import natural_sort_key


class AbstractClassTwoGalleries(QWidget, metaclass=MetaAbstractClassGallery):
    """
    Abstract base class for tabs with Found/Selected galleries.
    Lazy loading replaced with Sequential Loading: Images appear one by one.
    Includes Select All / Deselect All logic.
    """

    def __init__(self):
        super().__init__()

        # --- Data State ---
        self.found_files: List[str] = []
        self.selected_files: List[str] = []

        self.path_to_label_map: Dict[str, QWidget] = {}
        self.selected_card_map: Dict[str, QWidget] = {}
        self._selected_pixmap_cache = LRUImageCache(maxsize=200)
        self._found_pixmap_cache = LRUImageCache(maxsize=300)

        # --- Pagination State ---
        self.found_page_size = 150
        self.found_current_page = 0
        self.selected_page_size = 150
        self.selected_current_page = 0

        # --- UI Configuration ---
        self.thumbnail_size = self._load_thumbnail_size(default=180)
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20
        self._current_found_cols = 1
        self._current_selected_cols = 1

        # --- UI References ---
        self.found_gallery_scroll: Optional[MarqueeScrollArea] = None
        self.found_gallery_layout: Optional[QGridLayout] = None
        self.selected_gallery_scroll: Optional[MarqueeScrollArea] = None
        self.selected_gallery_layout: Optional[QGridLayout] = None
        self.status_label: Optional[QLabel] = None
        self.open_preview_windows: List[QWidget] = []

        # --- Threading ---
        self.thread_pool = QThreadPool.globalInstance()
        self._active_workers = set()

        # --- Population Timer (Sequential Loading) ---
        self._populate_found_timer = QTimer()
        self._populate_found_timer.setSingleShot(True)
        self._populate_found_timer.timeout.connect(self._populate_found_step)
        self._populating_found_index = 0

        # --- Resize Debouncing ---
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_layout_change)

        try:
            self.last_browsed_dir = self._load_last_dir(LOCAL_SOURCE_PATH)
        except Exception:
            self.last_browsed_dir = os.getcwd()

        # Flag so Ctrl+scroll zoom connections are wired once after gallery scrolls exist
        self._scroll_zoom_connected = False

        # §2.13A — sort state
        self._sort_key = "name"
        self._sort_reverse = False

        # Directory navigation history (GUI/UX §2.21A)
        self._dir_back_stack: deque = deque(maxlen=20)
        self._dir_forward_stack: deque = deque(maxlen=20)

        # --- Search State ---
        self.master_found_files: List[str] = []
        self.found_search_input = self.common_create_search_input(
            "Search found images..."
        )
        self.found_search_timer = QTimer()
        self.found_search_timer.setSingleShot(True)
        self.found_search_timer.setInterval(300)
        self.found_search_timer.timeout.connect(self._perform_found_search)
        self.found_search_input.textChanged.connect(self.found_search_timer.start)

        # Initialize Pagination Widgets using Shared Logic
        self.found_pagination_widget = self.create_pagination_controls(
            is_found_gallery=True
        )
        self.selected_pagination_widget = self.create_pagination_controls(
            is_found_gallery=False
        )

        # Enable keyboard focus for shortcuts
        self.setFocusPolicy(Qt.StrongFocus)

    # --- INLINE RENAME (GUI/UX §2.26B) ---
    def _rename_focused_file(self) -> None:
        """Rename the currently focused gallery item via F2 (GUI/UX §2.26B)."""
        idx = getattr(self, "_focused_found_idx", -1)
        page_paths = self.common_get_paginated_slice(
            self.master_found_files, self.found_current_page, self.found_page_size
        )
        if not (0 <= idx < len(page_paths)):
            return
        old_path = page_paths[idx]
        old_name = os.path.basename(old_path)
        stem, ext = os.path.splitext(old_name)

        new_stem, ok = QInputDialog.getText(
            self, "Rename File", "New name (no extension):", text=stem
        )
        if not ok or not new_stem.strip() or new_stem.strip() == stem:
            return

        new_stem = new_stem.strip()
        # Sanitise: remove characters illegal on common filesystems
        for ch in r'\/:*?"<>|':
            new_stem = new_stem.replace(ch, "_")

        new_path = os.path.join(os.path.dirname(old_path), new_stem + ext)
        if os.path.exists(new_path):
            QMessageBox.warning(
                self, "Rename", f"A file named '{new_stem + ext}' already exists."
            )
            return

        try:
            os.rename(old_path, new_path)
        except OSError as exc:
            QMessageBox.critical(self, "Rename Error", str(exc))
            return

        # Update all in-memory path lists and the label map
        self._replace_path_in_lists(old_path, new_path)

    def _replace_path_in_lists(self, old_path: str, new_path: str) -> None:
        """Swap *old_path* → *new_path* across found_files, master_found_files,
        selected_files, and path_to_label_map after a rename."""
        for lst in (self.found_files, self.master_found_files, self.selected_files):
            try:
                idx = lst.index(old_path)
                lst[idx] = new_path
            except ValueError:
                pass
        if old_path in self.path_to_label_map:
            widget = self.path_to_label_map.pop(old_path)
            self.path_to_label_map[new_path] = widget
            if hasattr(widget, "path"):
                widget.path = new_path
            if hasattr(widget, "file_path"):
                widget.file_path = new_path
            if hasattr(widget, "setToolTip"):
                widget.setToolTip(os.path.basename(new_path))

    # --- EXPORT SELECTION (GUI/UX §2.19A) ---
    def _export_selection_as_paths(self) -> None:
        """Write the currently selected file paths to a user-chosen TXT file (Ctrl+E)."""
        paths = self.selected_files or self.found_files
        if not paths:
            self._show_status("Nothing to export — gallery is empty.")
            return
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export File Paths",
            "",
            "Text files (*.txt);;CSV files (*.csv);;All files (*.*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not dest:
            return
        try:
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write("\n".join(paths))
            self._show_status(f"Exported {len(paths)} paths → {os.path.basename(dest)}")
        except OSError as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    # --- DIRECTORY NAVIGATION (GUI/UX §2.21A/D) ---
    def _navigate_to_dir(self, path: str) -> None:
        """Subclasses override to load *path* as the active gallery directory."""

    def _push_dir_history(self, path: str) -> None:
        """Call this before loading a new directory to push the current one to history."""
        if not path:
            return
        current = self.last_browsed_dir
        if current and (not self._dir_back_stack or self._dir_back_stack[-1] != current):
            self._dir_back_stack.append(current)
        self._dir_forward_stack.clear()

    def _dir_go_back(self) -> Optional[str]:
        """Return the previous directory, or None if no history."""
        if not self._dir_back_stack:
            return None
        prev = self._dir_back_stack.pop()
        self._dir_forward_stack.append(self.last_browsed_dir)
        return prev

    def _dir_go_forward(self) -> Optional[str]:
        """Return the next directory from the forward stack, or None."""
        if not self._dir_forward_stack:
            return None
        nxt = self._dir_forward_stack.pop()
        self._dir_back_stack.append(self.last_browsed_dir)
        return nxt

    # --- RECENT DIRECTORIES (GUI/UX §2.10) ---
    def _add_recent_dir(self, path: str, max_entries: int = 10) -> None:
        """Push *path* to the front of the per-class MRU directory list."""
        from gui.src.utils.settings import AppSettings
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
            from PySide6.QtWidgets import QApplication
            for widget in QApplication.topLevelWidgets():
                if hasattr(widget, "cached_creds"):
                    main_win = widget
                    break
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
            if not prefs.get("restore_last_dir", True):
                return []
        from gui.src.utils.settings import AppSettings
        return AppSettings.session(self.__class__.__name__, "recent_dirs", []) or []

    # --- SESSION PERSISTENCE (GUI/UX §2.5) ---
    def _save_last_dir(self, path: str) -> None:
        main_win = self.window()
        if not main_win:
            from PySide6.QtWidgets import QApplication
            for widget in QApplication.topLevelWidgets():
                if hasattr(widget, "cached_creds"):
                    main_win = widget
                    break
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
            if not prefs.get("restore_last_dir", True):
                return
        from gui.src.utils.settings import AppSettings
        AppSettings.set_session(self.__class__.__name__, "last_dir", path)

    def _load_last_dir(self, default: str = "") -> str:
        main_win = self.window()
        if not main_win:
            from PySide6.QtWidgets import QApplication
            for widget in QApplication.topLevelWidgets():
                if hasattr(widget, "cached_creds"):
                    main_win = widget
                    break
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
            if not prefs.get("restore_last_dir", True):
                return default
        from gui.src.utils.settings import AppSettings
        return AppSettings.session(self.__class__.__name__, "last_dir", default)

    # --- §2.14A — filename label below thumbnail ---
    def _add_filename_label(self, card: QWidget, path: str) -> None:
        """Append a truncated filename QLabel at the bottom of *card*'s layout (§2.14A)."""
        layout = card.layout()
        if layout is None:
            return
        name = os.path.basename(path)
        lbl = QLabel()
        lbl.setObjectName("thumb_filename_lbl")
        lbl.setAlignment(Qt.AlignCenter)
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
        # If the card has a fixed height already set (e.g. setFixedSize in subclass),
        # expand it to accommodate the label. Cards using QVBoxLayout without a prior
        # fixed height (height==0 at construction) are self-sizing — no adjustment needed.
        fixed_h = card.maximumHeight()
        if 0 < fixed_h < 16777215:  # 16777215 = Qt QWIDGETSIZE_MAX (no constraint)
            card.setFixedHeight(fixed_h + label_h)

    # --- §2.10C — status bar helper ---
    def _show_status(self, message: str, timeout_ms: int = 3000) -> None:
        """Post *message* to the main-window status bar (§2.10C)."""
        from ..windows.main_window import show_main_status
        show_main_status(message, timeout_ms)

    # --- THUMBNAIL SIZE PERSISTENCE (GUI/UX §4.11) ---
    def _save_thumbnail_size(self) -> None:
        from gui.src.utils.thumbnail_size import save_thumbnail_size
        save_thumbnail_size(self.__class__.__name__, self.thumbnail_size)

    def _load_thumbnail_size(self, default: int = 180) -> int:
        from gui.src.utils.thumbnail_size import load_thumbnail_size
        return load_thumbnail_size(self.__class__.__name__, default)

    def _sync_thumb_slider(self) -> None:
        """Push current thumbnail_size to both pagination sliders (after Ctrl+scroll)."""
        for attr in ("found_thumb_slider", "selected_thumb_slider"):
            slider = getattr(self, attr, None)
            if slider is not None:
                slider.blockSignals(True)
                slider.setValue(self.thumbnail_size)
                slider.blockSignals(False)
        for attr in ("found_thumb_size_lbl", "selected_thumb_size_lbl"):
            lbl = getattr(self, attr, None)
            if lbl is not None:
                lbl.setText(f"{self.thumbnail_size} px")

    # --- SORT (GUI/UX §2.13A) ---
    _SORT_KEY_MAP = {
        "Name": "name",
        "Date Modified": "mtime",
        "File Size": "size",
        "Extension": "ext",
    }

    def _sort_key_fn(self, path: str):
        from ..utils.sort_utils import natural_sort_key
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

    def _on_sort_combo_changed(self, label: str) -> None:
        self._sort_key = self._SORT_KEY_MAP.get(label, "name")
        self.master_found_files = self._apply_sort(self.master_found_files)
        self._perform_found_search()

    def _on_sort_dir_toggled(self, btn) -> None:
        self._sort_reverse = not self._sort_reverse
        btn.setText("↓" if self._sort_reverse else "↑")
        self.master_found_files = self._apply_sort(self.master_found_files)
        self._perform_found_search()

    # --- CTRL+SCROLL ZOOM (GUI/UX §2.2) ---
    def _connect_scroll_zoom(self) -> None:
        """Wire Ctrl+scroll zoom on gallery scroll areas (called lazily on first layout)."""
        if self._scroll_zoom_connected:
            return
        connected = False
        for scroll in (self.found_gallery_scroll, self.selected_gallery_scroll):
            if scroll is not None and hasattr(scroll, "ctrl_wheel"):
                scroll.ctrl_wheel.connect(self._on_ctrl_wheel_zoom)
                connected = True
        if connected:
            self._scroll_zoom_connected = True

    def _on_ctrl_wheel_zoom(self, delta: int) -> None:
        step = 16 if delta > 0 else -16
        new_size = max(64, min(512, self.thumbnail_size + step))
        if new_size == self.thumbnail_size:
            return
        self.thumbnail_size = new_size
        self.approx_item_width = new_size + self.padding_width + 20
        self._sync_thumb_slider()
        self._save_thumbnail_size()
        self._on_layout_change()
        current_page = self.common_get_paginated_slice(
            self.master_found_files, self.found_current_page, self.found_page_size
        )
        if current_page:
            self.start_loading_gallery(current_page)

    def _get_disk_cache_path(self, video_path: str) -> str:
        import hashlib
        THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path_hash = hashlib.md5(video_path.encode('utf-8')).hexdigest()
        return str(THUMBNAIL_CACHE_DIR / f"{path_hash}.jpg")

    # --- KEYBOARD SHORTCUTS (GUI/UX §2.29 — registry-driven) ---
    def keyPressEvent(self, event: QEvent):
        from ..utils.shortcut_manager import get_registry
        reg = get_registry()
        key = event.key()

        if reg.matches(event, "gallery.select_all"):
            self.select_all_items()
            event.accept()
        elif reg.matches(event, "gallery.deselect_all"):
            self.deselect_all_items()
            event.accept()
        elif reg.matches(event, "gallery.nav_left"):
            self._navigate_gallery(Qt.Key.Key_Left)
            event.accept()
        elif reg.matches(event, "gallery.nav_right"):
            self._navigate_gallery(Qt.Key.Key_Right)
            event.accept()
        elif reg.matches(event, "gallery.nav_up"):
            self._navigate_gallery(Qt.Key.Key_Up)
            event.accept()
        elif reg.matches(event, "gallery.nav_down"):
            self._navigate_gallery(Qt.Key.Key_Down)
            event.accept()
        elif reg.matches(event, "gallery.open_preview") or key == Qt.Key.Key_Space:
            self._preview_focused_item()
            event.accept()
        elif reg.matches(event, "gallery.export_paths"):
            self._export_selection_as_paths()
            event.accept()
        elif reg.matches(event, "gallery.copy_to_folder"):
            self._copy_selection_to_folder()
            event.accept()
        elif reg.matches(event, "gallery.rename"):
            self._rename_focused_file()
            event.accept()
        elif reg.matches(event, "gallery.nav_back"):
            prev = self._dir_go_back()
            if prev:
                self._navigate_to_dir(prev)
            event.accept()
        elif reg.matches(event, "gallery.nav_forward"):
            nxt = self._dir_go_forward()
            if nxt:
                self._navigate_to_dir(nxt)
            event.accept()
        else:
            super().keyPressEvent(event)

    # --- GALLERY NAVIGATION (GUI/UX §2.3A) ---
    def _navigate_gallery(self, key) -> None:
        """Move the gallery focus cursor with arrow keys."""
        page_paths = self.common_get_paginated_slice(
            self.master_found_files, self.found_current_page, self.found_page_size
        )
        if not page_paths:
            return

        cols = max(1, self._current_found_cols)
        idx = getattr(self, "_focused_found_idx", -1)

        if key == Qt.Key.Key_Right:
            idx = min(idx + 1, len(page_paths) - 1)
        elif key == Qt.Key.Key_Left:
            idx = max(0, idx - 1)
        elif key == Qt.Key.Key_Down:
            idx = min(idx + cols, len(page_paths) - 1)
        elif key == Qt.Key.Key_Up:
            idx = max(0, idx - cols)

        # Bootstrap: if nothing focused yet, start at 0
        if idx < 0:
            idx = 0

        self._focused_found_idx = idx
        self._highlight_focused(page_paths, idx)

    def _highlight_focused(self, page_paths: list, idx: int) -> None:
        """Visually highlight the focused thumbnail and scroll it into view."""
        target_path = page_paths[idx] if 0 <= idx < len(page_paths) else None
        if target_path is None:
            return
        widget = self.path_to_label_map.get(target_path)
        if widget:
            widget.setFocus()
            if self.found_gallery_scroll:
                self.found_gallery_scroll.ensureWidgetVisible(widget)

    def _preview_focused_item(self) -> None:
        """Open a preview for the currently focused gallery item.

        Delegates to the concrete tab by emitting `path_double_clicked` on the
        focused label widget, which concrete tabs already connect to their preview handler.
        """
        idx = getattr(self, "_focused_found_idx", -1)
        page_paths = self.common_get_paginated_slice(
            self.master_found_files, self.found_current_page, self.found_page_size
        )
        if 0 <= idx < len(page_paths):
            path = page_paths[idx]
            widget = self.path_to_label_map.get(path)
            if widget and hasattr(widget, "path_double_clicked"):
                widget.path_double_clicked.emit(path)

    @Slot()
    def select_all_items(self):
        """Selects all items currently visible on the current page."""
        # Calculate the slice for the current page using the common helper
        current_page_paths = self.common_get_paginated_slice(
            self.found_files, self.found_current_page, self.found_page_size
        )

        changed = False
        for path in current_page_paths:
            if path not in self.selected_files:
                self.selected_files.append(path)
                changed = True

        if changed:
            self.refresh_selected_panel()
            self._update_found_card_styles()
            self.on_selection_changed()

    @Slot()
    def deselect_all_items(self):
        """Clears the selection."""
        if self.selected_files:
            self.selected_files.clear()
            self.refresh_selected_panel()
            self._update_found_card_styles()
            self.on_selection_changed()

    def _update_found_card_styles(self):
        """Helper to re-evaluate and apply style to all currently loaded/visible found cards."""
        for path, widget in self.path_to_label_map.items():
            if widget:
                is_selected = path in self.selected_files
                self.update_card_style(widget, is_selected)

    # --- ABSTRACT METHODS ---

    @abstractmethod
    def create_card_widget(
        self, path: str, pixmap: Optional[QPixmap], is_selected: bool
    ) -> QWidget:
        pass

    @abstractmethod
    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        pass

    @abstractmethod
    def on_selection_changed(self):
        pass

    # --- PAGINATION UI HELPERS ---

    def create_pagination_controls(self, is_found_gallery: bool) -> QWidget:
        """Creates pagination using shared logic, then binds contextual signals."""
        container, controls = self.common_create_pagination_ui()

        # Center the controls horizontally (User request: bottom center)
        if container.layout():
            container.layout().setAlignment(Qt.AlignCenter)

        # Bind signals depending on context
        controls["combo"].currentTextChanged.connect(
            lambda text: self._on_page_size_changed(text, is_found_gallery)
        )
        controls["btn_prev"].clicked.connect(
            lambda: self._change_page(-1, is_found_gallery)
        )
        controls["btn_next"].clicked.connect(
            lambda: self._change_page(1, is_found_gallery)
        )

        # §4.11 — thumbnail slider
        slider = controls["thumb_slider"]
        size_lbl = controls["thumb_size_lbl"]
        slider.setValue(self.thumbnail_size)
        size_lbl.setText(f"{self.thumbnail_size} px")
        slider.valueChanged.connect(
            lambda v, f=is_found_gallery: self._on_thumb_slider_changed(v, f)
        )
        slider.sliderReleased.connect(self._save_thumbnail_size)

        # §2.13A — sort controls (wire once on the found gallery; applies globally)
        if is_found_gallery:
            sc = controls["sort_combo"]
            sd = controls["sort_dir_btn"]
            sc.currentTextChanged.connect(self._on_sort_combo_changed)
            sd.clicked.connect(lambda: self._on_sort_dir_toggled(sd))

        # Store references
        if is_found_gallery:
            self.found_page_button = controls["btn_page"]
            self.found_prev_btn = controls["btn_prev"]
            self.found_next_btn = controls["btn_next"]
            self.found_item_range_lbl = controls["item_range_lbl"]
            self.found_thumb_slider = slider
            self.found_thumb_size_lbl = size_lbl
        else:
            self.selected_page_button = controls["btn_page"]
            self.selected_prev_btn = controls["btn_prev"]
            self.selected_next_btn = controls["btn_next"]
            self.selected_item_range_lbl = controls["item_range_lbl"]
            self.selected_thumb_slider = slider
            self.selected_thumb_size_lbl = size_lbl

        return container

    def _on_page_size_changed(self, text: str, is_found: bool):
        size = 999999 if text == "All" else int(text)
        if is_found:
            self.found_page_size = size
            self.found_current_page = 0
            self.refresh_found_gallery()
        else:
            self.selected_page_size = size
            self.selected_current_page = 0
            self.refresh_selected_panel()

    def _on_thumb_slider_changed(self, value: int, is_found: bool) -> None:
        """Live thumbnail resize via slider (§4.11). Snaps to nearest 16px step."""
        snapped = max(64, min(512, (value // 16) * 16))
        if snapped == self.thumbnail_size:
            return
        self.thumbnail_size = snapped
        self.approx_item_width = snapped + self.padding_width + 20
        # Keep both sliders in sync
        self._sync_thumb_slider()
        self._on_layout_change()
        paths = self.common_get_paginated_slice(
            self.master_found_files if is_found else self.selected_files,
            self.found_current_page if is_found else self.selected_current_page,
            self.found_page_size if is_found else self.selected_page_size,
        )
        if paths:
            self.start_loading_gallery(paths)

    def _change_page(self, delta: int, is_found: bool):
        if is_found:
            total = len(self.found_files)
            max_p = math.ceil(total / self.found_page_size) - 1
            new_p = max(0, min(self.found_current_page + delta, max_p))
            if new_p != self.found_current_page:
                self.found_current_page = new_p
                self.refresh_found_gallery()
        else:
            total = len(self.selected_files)
            max_p = math.ceil(total / self.selected_page_size) - 1
            new_p = max(0, min(self.selected_current_page + delta, max_p))
            if new_p != self.selected_current_page:
                self.selected_current_page = new_p
                self.refresh_selected_panel()

    def _jump_to_page(self, page_index: int, is_found: bool):
        if is_found:
            if page_index != self.found_current_page:
                self.found_current_page = page_index
                self.refresh_found_gallery()
        else:
            if page_index != self.selected_current_page:
                self.selected_current_page = page_index
                self.refresh_selected_panel()

    def _update_pagination_ui(self, is_found: bool):
        if is_found:
            if not hasattr(self, "found_page_button"):
                return
            controls = {
                "btn_page": self.found_page_button,
                "btn_prev": self.found_prev_btn,
                "btn_next": self.found_next_btn,
            }
            total = len(self.found_files)
            size = self.found_page_size
            current = self.found_current_page
        else:
            if not hasattr(self, "selected_page_button"):
                return
            controls = {
                "btn_page": self.selected_page_button,
                "btn_prev": self.selected_prev_btn,
                "btn_next": self.selected_next_btn,
            }
            total = len(self.selected_files)
            size = self.selected_page_size
            current = self.selected_current_page

        # Shared State Update Logic
        corrected_page, total_pages = self.common_update_pagination_state(
            total, size, current, controls
        )

        if is_found:
            self.found_current_page = corrected_page
        else:
            self.selected_current_page = corrected_page

        # §3.9 — update item range label
        range_lbl = getattr(
            self, "found_item_range_lbl" if is_found else "selected_item_range_lbl", None
        )
        if range_lbl is not None:
            if total == 0:
                range_lbl.setText("0 images")
            else:
                first = corrected_page * size + 1
                last = min(first + size - 1, total)
                range_lbl.setText(f"Items {first}–{last} of {total}")

        # --- FIX: Prevent memory leak and crash by deleting the old menu safely ---
        old_menu = controls["btn_page"].menu()
        if old_menu:
            old_menu.deleteLater()

        # Update Menu
        menu = QMenu(self)
        for i in range(total_pages):
            action = QAction(f"Page {i + 1}", menu)  # Parent to menu instead of self
            action.setCheckable(True)
            action.setChecked(i == corrected_page)
            action.triggered.connect(
                lambda checked=False, p=i, f=is_found: self._jump_to_page(p, f)
            )
            menu.addAction(action)
        controls["btn_page"].setMenu(menu)

    # --- GEOMETRY & LAYOUT LOGIC ---

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start(100)  # 100ms debounce

    def _on_layout_change(self):
        self._connect_scroll_zoom()
        # Shared Calculation
        if self.found_gallery_scroll:
            new_cols = self.common_calculate_columns(
                self.found_gallery_scroll, self.approx_item_width
            )
            if new_cols != self._current_found_cols:
                self._current_found_cols = new_cols
                self.common_reflow_layout(self.found_gallery_layout, new_cols)

        if self.selected_gallery_scroll:
            new_cols = self.common_calculate_columns(
                self.selected_gallery_scroll, self.approx_item_width
            )
            if new_cols != self._current_selected_cols:
                self._current_selected_cols = new_cols
                self.common_reflow_layout(self.selected_gallery_layout, new_cols)

    # --- SELECTION LOGIC ---

    # §2.4B — Shift+click range select ----------------------------------
    @Slot(str)
    def _on_found_card_clicked(self, path: str) -> None:
        """Handle left-click on a found-gallery card, supporting Shift+range."""
        from PySide6.QtWidgets import QApplication as _QApp
        modifiers = _QApp.keyboardModifiers()
        page_paths = self.common_get_paginated_slice(
            self.master_found_files, self.found_current_page, self.found_page_size
        )
        try:
            clicked_idx = page_paths.index(path)
        except ValueError:
            self.toggle_selection(path)
            return

        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            anchor = getattr(self, "_selection_anchor_idx", clicked_idx)
            lo, hi = sorted([anchor, clicked_idx])
            for p in page_paths[lo : hi + 1]:
                if p not in self.selected_files:
                    self.selected_files.append(p)
            self._update_found_card_styles()
            self.refresh_selected_panel()
            self.on_selection_changed()
        else:
            self._selection_anchor_idx = clicked_idx
            self.toggle_selection(path)

    # §2.4C — right-click context menu on found-gallery cards -----------
    @Slot(object, str)
    def _on_found_card_right_clicked(self, global_pos, path: str) -> None:
        from PySide6.QtWidgets import QMenu as _QMenu
        from PySide6.QtGui import QAction as _QAct
        menu = _QMenu(self)

        open_act = _QAct("Open Preview", menu)
        open_act.triggered.connect(lambda: self._open_preview_for(path))
        menu.addAction(open_act)

        menu.addSeparator()

        sel_lbl = "Deselect" if path in self.selected_files else "Select"
        sel_act = _QAct(sel_lbl, menu)
        sel_act.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(sel_act)

        sel_all_act = _QAct("Select All", menu)
        sel_all_act.triggered.connect(self.select_all_items)
        menu.addAction(sel_all_act)

        desel_act = _QAct("Deselect All", menu)
        desel_act.triggered.connect(self.deselect_all_items)
        menu.addAction(desel_act)

        menu.addSeparator()

        rename_act = _QAct("Rename…  (F2)", menu)
        rename_act.triggered.connect(self._rename_focused_file)
        menu.addAction(rename_act)

        trash_act = _QAct("Move to Trash", menu)
        trash_act.triggered.connect(lambda: self._trash_path(path))
        menu.addAction(trash_act)

        menu.addSeparator()

        export_act = _QAct("Export Paths…  (Ctrl+E)", menu)
        export_act.triggered.connect(self._export_selection_as_paths)
        menu.addAction(export_act)

        copy_act = _QAct("Copy Selection to Folder…", menu)
        copy_act.triggered.connect(self._copy_selection_to_folder)
        menu.addAction(copy_act)

        menu.addSeparator()

        # Color label submenu (§2.18B)
        label_menu = menu.addMenu("Color Label")
        current_label = self._get_color_label(path)
        for key, hex_color in self._LABEL_COLORS.items():
            icon_txt = self._LABEL_ICONS.get(key, "")
            lbl_act = _QAct(f"{icon_txt} {key.capitalize()}", label_menu)
            lbl_act.setCheckable(True)
            lbl_act.setChecked(current_label == key)
            lbl_act.triggered.connect(
                lambda checked=False, k=key: self._set_color_label(
                    path, None if self._get_color_label(path) == k else k
                )
            )
            label_menu.addAction(lbl_act)
        label_menu.addSeparator()
        clear_act = _QAct("Clear Label", label_menu)
        clear_act.setEnabled(current_label is not None)
        clear_act.triggered.connect(lambda: self._set_color_label(path, None))
        label_menu.addAction(clear_act)

        menu.exec(global_pos)

    def _open_preview_for(self, path: str) -> None:
        widget = self.path_to_label_map.get(path)
        if widget and hasattr(widget, "path_double_clicked"):
            widget.path_double_clicked.emit(path)

    def _confirm_deletions_enabled(self) -> bool:
        """Return True if the user's preference requires a confirmation dialog before deletion (§2.9D)."""
        try:
            main_win = self.window()
            if main_win and hasattr(main_win, "cached_creds"):
                return bool(main_win.cached_creds.get("preferences", {}).get("confirm_deletions", True))
        except Exception:
            pass
        return True

    def _trash_path(self, path: str) -> None:
        if self._confirm_deletions_enabled():
            answer = QMessageBox.question(
                self,
                "Move to Trash",
                f'Move "{os.path.basename(path)}" to trash?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            from send2trash import send2trash
            send2trash(path)
        except Exception as exc:
            QMessageBox.critical(self, "Move to Trash", str(exc))
            return
        for lst in (self.found_files, self.master_found_files, self.selected_files):
            try:
                lst.remove(path)
            except ValueError:
                pass
        self.path_to_label_map.pop(path, None)
        self._update_found_card_styles()
        self.refresh_selected_panel()
        self.on_selection_changed()
        self._show_status(f"Moved to trash: {os.path.basename(path)}")

    def _copy_selection_to_folder(self) -> None:
        """Copy the current selection (or found list if no selection) to a chosen folder (§2.19C)."""
        import shutil
        paths = list(self.selected_files) if self.selected_files else list(self.found_files)
        if not paths:
            self._show_status("Nothing to copy — gallery is empty.")
            return
        dest_dir = QFileDialog.getExistingDirectory(
            self,
            "Copy Selection to Folder",
            "",
            QFileDialog.Option.DontUseNativeDialog,
        )
        if not dest_dir:
            return
        copied, skipped = 0, 0
        for src in paths:
            dst = os.path.join(dest_dir, os.path.basename(src))
            if os.path.exists(dst):
                skipped += 1
                continue
            try:
                shutil.copy2(src, dst)
                copied += 1
            except OSError as exc:
                QMessageBox.critical(self, "Copy Error", f"Failed to copy {os.path.basename(src)}:\n{exc}")
                return
        msg = f"Copied {copied} file(s) to {os.path.basename(dest_dir)}"
        if skipped:
            msg += f" ({skipped} skipped — already exist)"
        self._show_status(msg)

    @Slot(str)
    def toggle_selection(self, path: str):
        try:
            index = self.selected_files.index(path)
            self.selected_files.pop(index)
            selected = False
        except ValueError:
            self.selected_files.append(path)
            self.selected_files.sort(key=natural_sort_key)
            selected = True

        label = self.path_to_label_map.get(path)
        if label:
            try:
                self.update_card_style(label, selected)
            except RuntimeError:
                pass

        self.refresh_selected_panel()
        self.on_selection_changed()

    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        # Check for Shift modifier explicitly
        modifiers = QApplication.keyboardModifiers()
        is_shift_pressed = bool(modifiers & Qt.ShiftModifier)

        ordered_current = self.selected_files.copy()
        paths_to_update = set()

        if is_ctrl_pressed:
            # Subtractive selection (CTRL): Remove items in marquee from selection
            for path in paths_from_marquee:
                if path in self.selected_files:
                    self.selected_files.remove(path)
                    paths_to_update.add(path)

        elif is_shift_pressed:
            # Additive selection (SHIFT): Keep current selection, add new items from marquee
            newly_added = [p for p in paths_from_marquee if p not in ordered_current]
            self.selected_files = sorted(ordered_current + newly_added, key=natural_sort_key)
            paths_to_update = set(newly_added)

        else:
            # Standard selection (No Modifiers):
            # Replaces selection with what is currently in the marquee.
            paths_to_update = set(self.selected_files).union(paths_from_marquee)
            self.selected_files = sorted(list(paths_from_marquee), key=natural_sort_key)

        for path in paths_to_update:
            if path in self.path_to_label_map:
                widget = self.path_to_label_map[path]
                self.update_card_style(widget, path in self.selected_files)

        self.refresh_selected_panel()
        self.on_selection_changed()

    def is_path_selected(self, path: str) -> bool:
        """Returns True if the given path is currently selected."""
        return path in self.selected_files

    # --- COLOR LABELS (§2.18B+C) ---
    _LABEL_COLORS: Dict[str, str] = {
        "red":    "#e74c3c",
        "orange": "#e67e22",
        "yellow": "#f1c40f",
        "green":  "#2ecc71",
        "blue":   "#3498db",
        "purple": "#9b59b6",
    }
    _LABEL_ICONS: Dict[str, str] = {
        "red": "🔴", "orange": "🟠", "yellow": "🟡",
        "green": "🟢", "blue": "🔵", "purple": "🟣",
    }

    def _get_color_label(self, path: str) -> Optional[str]:
        """Return the color key for *path*, or None if unlabelled."""
        from gui.src.utils.settings import AppSettings
        return AppSettings.label(path)

    def _set_color_label(self, path: str, color_key: Optional[str]) -> None:
        """Persist *color_key* (or clear it) for *path*, then refresh the card border."""
        from gui.src.utils.settings import AppSettings
        if color_key:
            AppSettings.set_label(path, color_key)
        else:
            AppSettings.remove(f"labels/{path}")
        card = self.path_to_label_map.get(path)
        if card:
            self.update_card_style(card, path in self.selected_files)

    def update_card_style(self, widget: QWidget, is_selected: bool):
        if hasattr(widget, "set_selected_style"):
            widget.set_selected_style(is_selected)
        else:
            if is_selected:
                color, width = "#5865f2", "3px"
            else:
                # Show color label border when not selected (§2.18C)
                path = widget.property("gallery_path")
                label_color = self._LABEL_COLORS.get(self._get_color_label(path) or "", "") if path else ""
                color = label_color or "#4f545c"
                width = "2px" if label_color else "1px"
            widget.setStyleSheet(f"border: {width} solid {color};")

    @Slot(str, str)
    def update_preview_highlight(self, old_path: str, new_path: str):
        """Adds a blue highlight border to the card currently being viewed in the preview window."""
        is_closing = new_path == "WINDOW_CLOSED"

        def reset_card(path, card):
            if not card or not path:
                return
            try:
                orig = card.property("original_style")
                if orig is not None:
                    card.setStyleSheet(orig)
                    card.setProperty("original_style", None)
                else:
                    # Fallback: ensure the selection style is correct
                    self.update_card_style(card, self.is_path_selected(path))
            except RuntimeError:
                pass

        # 1. Restore style for the old card (found gallery and selected gallery)
        reset_card(old_path, self.path_to_label_map.get(old_path))
        reset_card(old_path, self.selected_card_map.get(old_path))

        if is_closing:
            sender_win = self.sender()
            if sender_win in self.open_preview_windows:
                self.open_preview_windows.remove(sender_win)
            return

        def highlight_card(path, card):
            if not card or not path:
                return
            try:
                # Ensure it has the correct selection state first
                self.update_card_style(card, self.is_path_selected(path))

                # Store style if not already stored
                if card.property("original_style") is None:
                    card.setProperty("original_style", card.styleSheet())

                # Apply blue highlight border to the card wrapper
                current = card.styleSheet().strip()
                sep = "" if not current or current.endswith(";") else ";"
                card.setStyleSheet(f"{current}{sep} border: 4px solid #3498db;")
            except RuntimeError:
                pass

        # 2. Apply highlight to the new card
        highlight_card(new_path, self.path_to_label_map.get(new_path))
        highlight_card(new_path, self.selected_card_map.get(new_path))

    def _cache_get_as_pixmap(self, path: str) -> Optional[QPixmap]:
        """Retrieve a cached thumbnail as QPixmap, converting from QImage if needed."""
        img = self._selected_pixmap_cache.get(path) or self._found_pixmap_cache.get(
            path
        )
        if img is None:
            return None
        return QPixmap.fromImage(img) if isinstance(img, QImage) else img

    def refresh_selected_panel(self):
        if not self.selected_gallery_layout:
            return

        # 1. Harvest pixmaps from current widgets to refresh cache
        for path, widget in self.selected_card_map.items():
            try:
                if hasattr(widget, "get_pixmap"):
                    pixmap = widget.get_pixmap()
                    if pixmap and not pixmap.isNull():
                        self._selected_pixmap_cache[path] = pixmap
            except RuntimeError:
                continue

        # 2. Identify new paginated slice
        paginated_paths = self.common_get_paginated_slice(
            self.selected_files, self.selected_current_page, self.selected_page_size
        )
        new_paths_set = set(paginated_paths)

        # 3. Identify and remove widgets not in the new slice
        paths_to_remove = [p for p in self.selected_card_map if p not in new_paths_set]
        for path in paths_to_remove:
            widget = self.selected_card_map.pop(path)
            widget.deleteLater()

        # 4. Update pagination
        self._update_pagination_ui(is_found=False)

        if not self.selected_files:
            # If empty, clear whatever is left and show placeholder
            self._clear_layout(self.selected_gallery_layout)
            self.common_show_placeholder(
                self.selected_gallery_layout, "Selected files will appear here.", 1
            )
            return

        # 5. Arrange/Create widgets
        columns = self.common_calculate_columns(
            self.selected_gallery_scroll, self.approx_item_width
        )
        paths_to_load = []
        target_widgets = {}

        for i, path in enumerate(paginated_paths):
            row = i // columns
            col = i % columns

            if path in self.selected_card_map:
                # Reuse existing widget
                card = self.selected_card_map[path]
                self.selected_gallery_layout.addWidget(
                    card, row, col, Qt.AlignLeft | Qt.AlignTop
                )
            else:
                # Create new widget
                pixmap = self._cache_get_as_pixmap(path)
                if pixmap is None:
                    top_widget = self.path_to_label_map.get(path)
                    if top_widget:
                        try:
                            if hasattr(top_widget, "get_pixmap"):
                                pixmap = top_widget.get_pixmap()
                        except RuntimeError:
                            pixmap = None

                card = self.create_card_widget(path, pixmap, is_selected=True)
                self._add_filename_label(card, path)  # §2.14A
                self.selected_card_map[path] = card
                self.selected_gallery_layout.addWidget(
                    card, row, col, Qt.AlignLeft | Qt.AlignTop
                )

                if pixmap is None:
                    paths_to_load.append(path)
                    target_widgets[path] = card

                if isinstance(card, ClickableLabel):
                    card.path_clicked.connect(
                        lambda checked, p=path: self.toggle_selection(p)
                    )

        if paths_to_load:
            self._trigger_batch_selected_load(paths_to_load, target_widgets)

    def _trigger_batch_selected_load(
        self, paths: List[str], widgets: Dict[str, QWidget]
    ):
        worker = BatchImageLoaderWorker(paths, self.thumbnail_size)
        worker.signals.batch_result.connect(
            lambda results: self._on_batch_selected_loaded(results, widgets)
        )
        self.thread_pool.start(worker)

    def _on_batch_selected_loaded(
        self, results: List[tuple], widgets: Dict[str, QWidget]
    ):
        for path, image in results:
            if image and not image.isNull():
                self._selected_pixmap_cache[path] = image  # store QImage

                # Save to disk cache if it's a video
                if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                    cache_path = self._get_disk_cache_path(path)
                    if not os.path.exists(cache_path):
                        image.save(cache_path, "JPG")
            widget = widgets.get(path)
            if widget:
                try:
                    display_pixmap = (
                        QPixmap.fromImage(image) if isinstance(image, QImage) else image
                    )
                    self.update_card_pixmap(widget, display_pixmap)
                except RuntimeError:
                    pass

    def _trigger_priority_load(self, path: str, target_widget: QWidget):
        import weakref

        weak_widget = weakref.ref(target_widget)
        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(
            lambda p, px: self._on_selected_image_loaded(p, px, weak_widget())
            if weak_widget() is not None
            else None
        )
        self.thread_pool.start(worker)

    def _on_selected_image_loaded(self, path: str, image, widget: Optional[QWidget]):
        if widget is None:
            return
        if image and not image.isNull():
            self._selected_pixmap_cache[path] = image  # store QImage

            # Save to disk cache if it's a video
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                cache_path = self._get_disk_cache_path(path)
                if not os.path.exists(cache_path):
                    if isinstance(image, QImage):
                        image.save(cache_path, "JPG")
                    else:
                        image.toImage().save(cache_path, "JPG")
        display_pixmap = (
            QPixmap.fromImage(image) if isinstance(image, QImage) else image
        )
        self.update_card_pixmap(widget, display_pixmap)

    # --- SEQUENTIAL LOADING (Found Gallery) ---

    def _perform_found_search(self):
        query = self.found_search_input.text()
        filtered = self.common_filter_string_list(self.master_found_files, query)
        self.found_files = filtered
        self.found_current_page = 0
        self.refresh_found_gallery()

    def start_loading_thumbnails(self, paths: list[str]):
        self.cancel_loading()
        self.master_found_files = self._apply_sort(list(paths))
        # Clear cache when starting fresh with new content
        self._found_pixmap_cache.clear()
        # Apply search immediately
        self._perform_found_search()
        # self.refresh_found_gallery() # Called by search

    def _trigger_batch_video_found_load(self, paths: List[str]):
        """Trigger a single batch worker for all visible videos."""
        if not hasattr(self, "found_loading_paths"):
            self.found_loading_paths = set()

        self.found_loading_paths.update(paths)
        worker = BatchVideoLoaderWorker(paths, self.thumbnail_size)

        # Connect both signals: result for individual updates, batch_result for cleanup if needed
        worker.signals.result.connect(self._on_found_image_loaded)
        # Note: we don't strictly need batch_result here as _on_found_image_loaded handles individual cleanup

        self.thread_pool.start(worker)

    def _trigger_video_found_load(self, path: str):
        """Fallback for single video load (rarely used by batch logic but kept for consistency)."""
        if not hasattr(self, "found_loading_paths"):
            self.found_loading_paths = set()

        self.found_loading_paths.add(path)
        worker = VideoLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(self._on_found_image_loaded)
        self.thread_pool.start(worker)

    @Slot(str, object)
    def _on_found_image_loaded(self, path: str, image):
        # Cleanup worker ref
        sender = self.sender()
        if sender:
            # We need to find the worker that owns this signals object
            for worker in list(self._active_workers):
                if worker.signals == sender:
                    self._active_workers.remove(worker)
                    break

        if hasattr(self, "found_loading_paths") and path in self.found_loading_paths:
            self.found_loading_paths.remove(path)

        # Cache QImage (half the memory of QPixmap on X11)
        if isinstance(image, QImage) and not image.isNull():
            self._found_pixmap_cache[path] = image
            # Save to disk cache if it's a video
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                cache_path = self._get_disk_cache_path(path)
                if not os.path.exists(cache_path):
                    image.save(cache_path, "JPG")
        elif not isinstance(image, QImage) and image and not image.isNull():
            q_image = image.toImage()
            self._found_pixmap_cache[path] = q_image
            # Save to disk cache if it's a video
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                cache_path = self._get_disk_cache_path(path)
                if not os.path.exists(cache_path):
                    q_image.save(cache_path, "JPG")

        widget = self.path_to_label_map.get(path)
        if widget:
            try:
                if isinstance(image, QImage):
                    pixmap = QPixmap.fromImage(image)
                else:
                    pixmap = image

                if pixmap.isNull():
                    # Explicitly handle failure instead of resetting to "Loading..."
                    img_label = widget.findChild(QLabel)
                    if img_label:
                        img_label.clear()
                        img_label.setText("No Thumbnail")
                        img_label.setStyleSheet("border: 1px dashed #666; color: #999;")
                else:
                    self.update_card_pixmap(widget, pixmap)
            except RuntimeError:
                pass

    def _trigger_batch_found_load(self, paths: List[str]):
        if not hasattr(self, "found_loading_paths"):
            self.found_loading_paths = set()
        self.found_loading_paths.update(paths)
        worker = BatchImageLoaderWorker(paths, self.thumbnail_size)
        worker.signals.result.connect(self._on_found_image_loaded)
        worker.signals.batch_result.connect(self._on_batch_found_loaded)

        self._active_workers.add(worker)
        self.thread_pool.start(worker)

    @Slot(list, list)
    def _on_batch_found_loaded(self, results: List[tuple], requested_paths: List[str]):
        # Cleanup worker ref
        sender = self.sender()
        if sender:
            for worker in list(self._active_workers):
                if worker.signals == sender:
                    self._active_workers.remove(worker)
                    break

        for path, pixmap in results:
            if (
                hasattr(self, "found_loading_paths")
                and path in self.found_loading_paths
            ):
                self.found_loading_paths.remove(path)
            elif path in getattr(self, "_loading_paths", set()):
                self._loading_paths.remove(path)

            # Cache QImage, convert to QPixmap for display only
            if isinstance(pixmap, QImage) and not pixmap.isNull():
                self._found_pixmap_cache[path] = pixmap  # store QImage
                final_pixmap = QPixmap.fromImage(pixmap)
                # Save to disk cache if it's a video
                if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                    cache_path = self._get_disk_cache_path(path)
                    if not os.path.exists(cache_path):
                        pixmap.save(cache_path, "JPG")
            elif not isinstance(pixmap, QImage) and pixmap and not pixmap.isNull():
                q_image = pixmap.toImage()
                self._found_pixmap_cache[path] = q_image
                final_pixmap = pixmap
                # Save to disk cache if it's a video
                if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                    cache_path = self._get_disk_cache_path(path)
                    if not os.path.exists(cache_path):
                        q_image.save(cache_path, "JPG")
            else:
                final_pixmap = QPixmap()

            widget = self.path_to_label_map.get(path)
            if widget:
                try:
                    self.update_card_pixmap(widget, final_pixmap)
                except RuntimeError:
                    pass

    def refresh_found_gallery(self):
        self.cancel_loading()

        if not hasattr(self, "found_loading_paths"):
            self.found_loading_paths = set()
        self.found_loading_paths.clear()

        # 1. Identify new paginated slice
        self._paginated_found_paths = self.common_get_paginated_slice(
            self.found_files, self.found_current_page, self.found_page_size
        )
        new_paths_set = set(self._paginated_found_paths)

        # 2. Identify which currently displayed widgets to REMOVE
        paths_to_remove = []
        for path in list(self.path_to_label_map.keys()):
            if path not in new_paths_set:
                paths_to_remove.append(path)

        for path in paths_to_remove:
            widget = self.path_to_label_map.pop(path)
            widget.deleteLater()

        # 3. Reflow and Pagination update
        self._update_pagination_ui(is_found=True)

        if not self.found_files:
            self.common_show_placeholder(
                self.found_gallery_layout, "No images found.", 1
            )
            if self.status_label:
                self.status_label.setText("Found 0 files.")
            return

        # Setup batch population
        self._paginated_found_paths = self.common_get_paginated_slice(
            self.found_files, self.found_current_page, self.found_page_size
        )
        self._populating_found_index = 0

        if self.status_label:
            self.status_label.setText(
                f"Found {len(self.found_files)} files. Showing page {self.found_current_page + 1}."
            )

        # Start population loop
        self._populate_found_step()

    def _populate_found_step(self):
        if not hasattr(
            self, "_paginated_found_paths"
        ) or self._populating_found_index >= len(self._paginated_found_paths):
            self._load_all_found_page_images()
            return

        cols = self.common_calculate_columns(
            self.found_gallery_scroll, self.approx_item_width
        )
        batch_size = 5
        limit = min(
            self._populating_found_index + batch_size, len(self._paginated_found_paths)
        )

        for i in range(self._populating_found_index, limit):
            path = self._paginated_found_paths[i]

            # If widget already exists (was kept during refresh), just update its position
            if path in self.path_to_label_map:
                card = self.path_to_label_map[path]
                row = i // cols
                col = i % cols
                if self.found_gallery_layout:
                    # addWidget will move it if it's already in the layout
                    self.found_gallery_layout.addWidget(
                        card, row, col, Qt.AlignLeft | Qt.AlignTop
                    )
                continue

            # Otherwise create new widget
            is_selected = path in self.selected_files

            # Check cache for instant thumbnail (stored as QImage, convert for widget)
            _cached = self._found_pixmap_cache.get(path)

            if _cached is None and path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                cache_path = self._get_disk_cache_path(path)
                if os.path.exists(cache_path):
                    _cached = QImage(cache_path)
                    if not _cached.isNull():
                        self._found_pixmap_cache[path] = _cached

            initial_pixmap = (
                QPixmap.fromImage(_cached) if isinstance(_cached, QImage) else _cached
            )

            # Create widget
            card = self.create_card_widget(path, initial_pixmap, is_selected)
            card.setProperty("gallery_path", path)  # used by update_card_style for color labels (§2.18C)

            if isinstance(card, ClickableLabel):
                card.path_clicked.connect(self._on_found_card_clicked)  # §2.4B
                if hasattr(card, "path_right_clicked"):
                    card.path_right_clicked.connect(self._on_found_card_right_clicked)  # §2.4C

            self._add_filename_label(card, path)  # §2.14A

            row = i // cols
            col = i % cols
            if self.found_gallery_layout:
                self.found_gallery_layout.addWidget(
                    card, row, col, Qt.AlignLeft | Qt.AlignTop
                )

            self.path_to_label_map[path] = card

            # DEFER Trigger load
            # self._trigger_found_load(path)

        self._populating_found_index = limit

        # Schedule next batch
        if self._populating_found_index < len(self._paginated_found_paths):
            self._populate_found_timer.start(0)
        else:
            self._load_all_found_page_images()

    def _load_all_found_page_images(self):
        """Triggers loading for all images in the current found gallery paginated view."""
        if (
            not hasattr(self, "_paginated_found_paths")
            or not self._paginated_found_paths
        ):
            return

        paths_to_load = []
        for path in self._paginated_found_paths:
            if path in self._found_pixmap_cache:
                continue
            if (
                hasattr(self, "found_loading_paths")
                and path in self.found_loading_paths
            ):
                continue
            paths_to_load.append(path)

        if not paths_to_load:
            return

        # Separate images and videos
        image_paths = [
            p
            for p in paths_to_load
            if not p.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        ]
        video_paths = [
            p
            for p in paths_to_load
            if p.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        ]

        if video_paths:
            for p in video_paths:
                self._trigger_video_found_load(p)

        if image_paths:
            self._trigger_batch_found_load(image_paths)

    def _trigger_found_load(self, path: str):
        if not hasattr(self, "found_loading_paths"):
            self.found_loading_paths = set()

        self.found_loading_paths.add(path)
        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(self._on_found_image_loaded)

        self._active_workers.add(worker)
        self.thread_pool.start(worker)

    # _on_found_image_loaded is defined earlier to handle QImage/QPixmap types

    # --- HELPERS ---

    def cancel_loading(self):
        """Stops all active timers and background workers."""
        if self._populate_found_timer.isActive():
            self._populate_found_timer.stop()
        if self._resize_timer.isActive():
            self._resize_timer.stop()
        if hasattr(self, "found_search_timer") and self.found_search_timer.isActive():
            self.found_search_timer.stop()

        # Stop all active workers
        for worker in list(self._active_workers):
            try:
                worker.stop()
            except Exception:
                pass
        self._active_workers.clear()

        if hasattr(self, "thread_pool"):
            self.thread_pool.clear()

    def closeEvent(self, event):
        """Cleanup processes on close."""
        self.cancel_loading()
        # Clean up pool
        self.thread_pool.clear()
        # Ensure signals don't fire to a destroyed object
        self.thread_pool.waitForDone(500)  # Short wait for safety
        super().closeEvent(event)

    def clear_galleries(self, clear_data=True):
        if clear_data:
            self.found_files.clear()
            self.selected_files.clear()
            self.path_to_label_map.clear()
            self.found_current_page = 0
            self.selected_current_page = 0
            self._selected_pixmap_cache.clear()

        self.cancel_loading()
        self._clear_layout(self.found_gallery_layout)
        self.common_show_placeholder(
            self.found_gallery_layout, "No images found/loaded.", 1
        )
        self._update_pagination_ui(is_found=True)

        self._clear_layout(self.selected_gallery_layout)
        self.common_show_placeholder(
            self.selected_gallery_layout, "Selected files will appear here.", 1
        )
        self._update_pagination_ui(is_found=False)

        self.on_selection_changed()

    def _restore_selected_files(self, config: dict):
        """Restores the selected gallery from a saved config, skipping missing paths."""
        saved = config.get("selected_files", [])
        if not saved:
            return
        valid = [p for p in saved if os.path.isfile(p)]
        if valid:
            self.selected_files = valid
            self.refresh_selected_panel()
            self.on_selection_changed()

    def _clear_layout(self, layout: QGridLayout):
        if not layout:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
