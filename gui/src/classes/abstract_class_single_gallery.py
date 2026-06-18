import os
import math
from collections import deque
from abc import abstractmethod
from typing import List, Optional, Dict
from PySide6.QtCore import Qt, Slot, QThreadPool, QTimer, QEvent
from PySide6.QtGui import QPixmap, QResizeEvent, QAction, QImage, QPainter, QColor
from PySide6.QtWidgets import (
    QWidget,
    QGridLayout,
    QScrollArea,
    QMenu,
    QLabel,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
    QInputDialog,
)
from backend.src.constants import (
    LOCAL_SOURCE_PATH,
    SUPPORTED_VIDEO_FORMATS,
    THUMBNAIL_CACHE_DIR,
)
from .meta_abstract_class_gallery import MetaAbstractClassGallery
from ..utils.lru_image_cache import LRUImageCache
from ..helpers import (
    ImageLoaderWorker,
    BatchImageLoaderWorker,
    VideoLoaderWorker,
)
from ..helpers.video.video_scan_worker import VideoThumbnailer
from ..utils.sort_utils import natural_sort_key


class AbstractClassSingleGallery(QWidget, metaclass=MetaAbstractClassGallery):
    """
    Abstract base class for a single gallery using MetaAbstractClassGallery.
    Includes built-in support for video thumbnail generation.
    """

    def __init__(self):
        super().__init__()

        # --- Data State ---
        self.gallery_image_paths: List[str] = []
        self.selected_files: List[str] = []
        self.path_to_card_widget: Dict[str, QWidget] = {}
        # Stores pre-generated or cached thumbnails (bounded LRU, stores QImage)
        self._initial_pixmap_cache = LRUImageCache(maxsize=300)

        # --- Pagination State ---
        self.page_size = 150
        self.current_page = 0

        # --- UI Configuration ---
        self.thumbnail_size = self._load_thumbnail_size(default=180)
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20
        self._current_cols = 1

        self.thread_pool = QThreadPool.globalInstance()
        self._active_workers = set()

        # --- Resize Debouncing ---
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_layout_change)

        # --- Population Timer ---
        self._populate_timer = QTimer()
        self._populate_timer.setSingleShot(True)
        self._populate_timer.timeout.connect(self._populate_step)
        self._paginated_paths: List[str] = []
        self._populating_index = 0

        # --- Keyboard Navigation (§2.3A) ---
        self._focused_idx: int = -1

        # --- UI References ---
        self.gallery_scroll_area: Optional[QScrollArea] = None
        self.gallery_layout: Optional[QGridLayout] = None
        self.open_preview_windows: List[QWidget] = []

        # --- Lazy Loading State ---
        self._loading_paths = set()
        self._failed_paths = set()

        # Starting directory — restored from QSettings if available (GUI/UX §2.5)
        try:
            self.last_browsed_scan_dir = self._load_last_dir(str(LOCAL_SOURCE_PATH))
        except Exception:
            self.last_browsed_scan_dir = os.getcwd()

        self._scroll_zoom_connected = False

        # §2.13A — sort state
        self._sort_key = "name"
        self._sort_reverse = False

        # Directory navigation history (GUI/UX §2.21A)
        self._dir_back_stack: deque = deque(maxlen=20)
        self._dir_forward_stack: deque = deque(maxlen=20)

        # --- Search State ---
        self.master_image_paths: List[str] = []
        self.search_input = self.common_create_search_input()
        self.search_debounce_timer = QTimer()
        self.search_debounce_timer.setSingleShot(True)
        self.search_debounce_timer.setInterval(300)
        self.search_debounce_timer.timeout.connect(self._perform_search)
        self.search_input.textChanged.connect(self.search_debounce_timer.start)

        # Initialize Pagination Widgets using Shared Logic
        self.pagination_widget = self.create_pagination_controls()

        # Enable keyboard focus for shortcuts
        self.setFocusPolicy(Qt.StrongFocus)

    # --- INLINE RENAME (GUI/UX §2.26B) ---
    def _rename_selected_file(self) -> None:
        """Rename the most-recently-selected gallery item via F2 (GUI/UX §2.26B)."""
        target = self.selected_files[-1] if self.selected_files else None
        if target is None and self.gallery_image_paths:
            target = self.gallery_image_paths[0]  # fallback: first visible
        if not target:
            return

        old_name = os.path.basename(target)
        stem, ext = os.path.splitext(old_name)
        new_stem, ok = QInputDialog.getText(
            self, "Rename File", "New name (no extension):", text=stem
        )
        if not ok or not new_stem.strip() or new_stem.strip() == stem:
            return

        new_stem = new_stem.strip()
        for ch in r'\/:*?"<>|':
            new_stem = new_stem.replace(ch, "_")

        new_path = os.path.join(os.path.dirname(target), new_stem + ext)
        if os.path.exists(new_path):
            QMessageBox.warning(
                self, "Rename", f"A file named '{new_stem + ext}' already exists."
            )
            return

        try:
            os.rename(target, new_path)
        except OSError as exc:
            QMessageBox.critical(self, "Rename Error", str(exc))
            return

        for lst in (self.gallery_image_paths, self.master_image_paths, self.selected_files):
            try:
                idx = lst.index(target)
                lst[idx] = new_path
            except (ValueError, AttributeError):
                pass

        widget = getattr(self, "path_to_card_widget", {}).pop(target, None)
        if widget is not None:
            self.path_to_card_widget[new_path] = widget
            if hasattr(widget, "path"):
                widget.path = new_path
            if hasattr(widget, "setToolTip"):
                widget.setToolTip(os.path.basename(new_path))

    # --- EXPORT (GUI/UX §2.19A) ---
    def _export_selection_as_paths(self) -> None:
        """Write selected (or all visible) paths to a TXT file (Ctrl+E)."""
        paths = self.selected_files or self.gallery_image_paths
        if not paths:
            QMessageBox.information(self, "Export", "No files to export.")
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
            QMessageBox.information(
                self, "Export", f"Exported {len(paths)} paths to:\n{dest}"
            )
        except OSError as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    def _copy_selection_to_folder(self) -> None:
        """Copy the current selection (or all visible) to a chosen folder (§2.19C)."""
        import shutil
        paths = list(self.selected_files) if self.selected_files else list(self.gallery_image_paths)
        if not paths:
            QMessageBox.information(self, "Copy to Folder", "No files to copy.")
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
        QMessageBox.information(self, "Copy to Folder", msg)

    # --- DIRECTORY NAVIGATION HISTORY (GUI/UX §2.21A) ---
    def _push_dir_history(self, path: str) -> None:
        if not path:
            return
        current = self.last_browsed_scan_dir
        if current and (not self._dir_back_stack or self._dir_back_stack[-1] != current):
            self._dir_back_stack.append(current)
        self._dir_forward_stack.clear()

    def _dir_go_back(self) -> Optional[str]:
        if not self._dir_back_stack:
            return None
        prev = self._dir_back_stack.pop()
        self._dir_forward_stack.append(self.last_browsed_scan_dir)
        return prev

    def _dir_go_forward(self) -> Optional[str]:
        if not self._dir_forward_stack:
            return None
        nxt = self._dir_forward_stack.pop()
        self._dir_back_stack.append(self.last_browsed_scan_dir)
        return nxt

    # --- RECENT DIRECTORIES (GUI/UX §2.10) ---
    def _add_recent_dir(self, path: str, max_entries: int = 10) -> None:
        from gui.src.utils.settings import AppSettings
        cn = self.__class__.__name__
        dirs: list = AppSettings.session(cn, "recent_dirs", []) or []
        if path in dirs:
            dirs.remove(path)
        dirs.insert(0, path)
        AppSettings.set_session(cn, "recent_dirs", dirs[:max_entries])

    def _get_recent_dirs(self) -> list:
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

    # --- §2.10C — status bar helper ---
    def _show_status(self, message: str, timeout_ms: int = 3000) -> None:
        from ..windows.main_window import show_main_status
        show_main_status(message, timeout_ms)

    # --- §2.14A — filename label below thumbnail ---
    def _add_filename_label(self, card: "QWidget", path: str) -> None:
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import Qt
        layout = card.layout()
        if layout is None:
            return
        name = os.path.basename(path)
        lbl = QLabel()
        lbl.setObjectName("thumb_filename_lbl")
        lbl.setAlignment(Qt.AlignCenter)
        max_w = self.thumbnail_size + 10
        fm = lbl.fontMetrics()
        elided = fm.elidedText(name, Qt.TextElideMode.ElideMiddle, max_w)
        lbl.setText(elided)
        lbl.setToolTip(name)
        lbl.setMaximumWidth(max_w)
        lbl.setStyleSheet(
            "color: #bbb; font-size: 8pt; padding: 0 2px; background: transparent;"
        )
        layout.addWidget(lbl)

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
        self.master_image_paths = self._apply_sort(self.master_image_paths)
        self._perform_search()

    def _on_sort_dir_toggled(self, btn) -> None:
        self._sort_reverse = not self._sort_reverse
        btn.setText("↓" if self._sort_reverse else "↑")
        self.master_image_paths = self._apply_sort(self.master_image_paths)
        self._perform_search()

    # --- THUMBNAIL SIZE PERSISTENCE (GUI/UX §4.11) ---
    def _save_thumbnail_size(self) -> None:
        from gui.src.utils.thumbnail_size import save_thumbnail_size
        save_thumbnail_size(self.__class__.__name__, self.thumbnail_size)

    def _load_thumbnail_size(self, default: int = 180) -> int:
        from gui.src.utils.thumbnail_size import load_thumbnail_size
        return load_thumbnail_size(self.__class__.__name__, default)

    def _sync_thumb_slider(self) -> None:
        """Push current thumbnail_size to the pagination slider after Ctrl+scroll."""
        slider = getattr(self, "thumb_slider", None)
        if slider is not None:
            slider.blockSignals(True)
            slider.setValue(self.thumbnail_size)
            slider.blockSignals(False)
        lbl = getattr(self, "thumb_size_lbl", None)
        if lbl is not None:
            lbl.setText(f"{self.thumbnail_size} px")

    # --- CTRL+SCROLL ZOOM (GUI/UX §2.2) ---
    def _connect_scroll_zoom(self) -> None:
        if self._scroll_zoom_connected:
            return
        if self.gallery_scroll_area is not None and hasattr(
            self.gallery_scroll_area, "ctrl_wheel"
        ):
            self.gallery_scroll_area.ctrl_wheel.connect(self._on_ctrl_wheel_zoom)
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
            self.master_image_paths, self.current_page, self.page_size
        )
        if current_page:
            self.start_loading_gallery(current_page)

    def _get_disk_cache_path(self, video_path: str) -> str:
        import hashlib
        THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path_hash = hashlib.md5(video_path.encode('utf-8')).hexdigest()
        return str(THUMBNAIL_CACHE_DIR / f"{path_hash}.jpg")

    # --- ABSTRACT METHODS ---

    @abstractmethod
    def create_gallery_label(self, path: str, size: int) -> QLabel:
        """Create the specific interactive label for a gallery item (subclass must implement)."""
        pass

    def on_selection_changed(self):
        """Optional hook for subclasses to react to selection changes."""
        pass

    # --- KEYBOARD NAVIGATION (§2.3A) ---
    def _navigate_gallery(self, key) -> None:
        """Move the gallery focus cursor with arrow keys (§2.3A)."""
        from PySide6.QtCore import Qt as _Qt
        page_paths = self.common_get_paginated_slice(
            self.gallery_image_paths, self.current_page, self.page_size
        )
        if not page_paths:
            return
        cols = max(1, self._current_cols)
        idx = self._focused_idx
        if key == _Qt.Key.Key_Right:
            idx = min(idx + 1, len(page_paths) - 1)
        elif key == _Qt.Key.Key_Left:
            idx = max(0, idx - 1)
        elif key == _Qt.Key.Key_Down:
            idx = min(idx + cols, len(page_paths) - 1)
        elif key == _Qt.Key.Key_Up:
            idx = max(0, idx - cols)
        if idx < 0:
            idx = 0
        self._focused_idx = idx
        self._highlight_focused(page_paths, idx)

    def _highlight_focused(self, page_paths: list, idx: int) -> None:
        target_path = page_paths[idx] if 0 <= idx < len(page_paths) else None
        if target_path is None:
            return
        widget = self.path_to_card_widget.get(target_path)
        if widget:
            widget.setFocus()
            if self.gallery_scroll_area:
                self.gallery_scroll_area.ensureWidgetVisible(widget)

    def _preview_focused_item(self) -> None:
        """Open a preview for the keyboard-focused gallery item."""
        page_paths = self.common_get_paginated_slice(
            self.gallery_image_paths, self.current_page, self.page_size
        )
        idx = self._focused_idx
        if 0 <= idx < len(page_paths):
            path = page_paths[idx]
            widget = self.path_to_card_widget.get(path)
            if widget and hasattr(widget, "path_double_clicked"):
                widget.path_double_clicked.emit(path)

    # --- KEYBOARD SHORTCUTS (GUI/UX §2.29 — registry-driven) ---
    def keyPressEvent(self, event: QEvent):
        from PySide6.QtCore import Qt as _Qt
        from ..utils.shortcut_manager import get_registry
        reg = get_registry()

        if reg.matches(event, "gallery.select_all"):
            self.select_all_items()
            event.accept()
        elif reg.matches(event, "gallery.deselect_all"):
            self.deselect_all_items()
            event.accept()
        elif reg.matches(event, "gallery.export_paths"):
            self._export_selection_as_paths()
            event.accept()
        elif reg.matches(event, "gallery.copy_to_folder"):
            self._copy_selection_to_folder()
            event.accept()
        elif reg.matches(event, "gallery.nav_left"):
            self._navigate_gallery(_Qt.Key.Key_Left)
            event.accept()
        elif reg.matches(event, "gallery.nav_right"):
            self._navigate_gallery(_Qt.Key.Key_Right)
            event.accept()
        elif reg.matches(event, "gallery.nav_up"):
            self._navigate_gallery(_Qt.Key.Key_Up)
            event.accept()
        elif reg.matches(event, "gallery.nav_down"):
            self._navigate_gallery(_Qt.Key.Key_Down)
            event.accept()
        elif reg.matches(event, "gallery.open_preview") or event.key() == _Qt.Key.Key_Space:
            self._preview_focused_item()
            event.accept()
        elif reg.matches(event, "gallery.rename"):
            self._rename_selected_file()
            event.accept()
        else:
            super().keyPressEvent(event)

    @Slot()
    def select_all_items(self):
        """Selects all items currently visible on the current page."""
        paginated_paths = self.common_get_paginated_slice(
            self.gallery_image_paths, self.current_page, self.page_size
        )

        changed = False
        for path in paginated_paths:
            if path not in self.selected_files:
                self.selected_files.append(path)
                changed = True

        if changed:
            # Update styles for all visible widgets
            for path in paginated_paths:
                widget = self.path_to_card_widget.get(path)
                if widget:
                    self.update_card_style(widget, True)
            self.on_selection_changed()

    @Slot()
    def deselect_all_items(self):
        """Clears the selection."""
        if self.selected_files:
            affected_paths = list(self.selected_files)
            self.selected_files.clear()
            # Update styles for visible widgets that were selected
            paginated_paths = self.common_get_paginated_slice(
                self.gallery_image_paths, self.current_page, self.page_size
            )
            for path in paginated_paths:
                if path in affected_paths:
                    widget = self.path_to_card_widget.get(path)
                    if widget:
                        self.update_card_style(widget, False)
            self.on_selection_changed()

    @Slot(str)
    def toggle_selection(self, path: str):
        """Toggle the selection state of a gallery item."""
        if path in self.selected_files:
            self.selected_files.remove(path)
            selected = False
        else:
            self.selected_files.append(path)
            selected = True

        widget = self.path_to_card_widget.get(path)
        if widget:
            label = widget.findChild(QLabel)
            if label:
                self.update_card_style(widget, selected)

        self.on_selection_changed()

    def is_path_selected(self, path: str) -> bool:
        """Returns True if the given path is currently selected."""
        return path in self.selected_files

    def update_card_style(self, widget: QWidget, is_selected: bool):
        """Updates the visual style of a card based on selection state."""
        label = widget.findChild(QLabel)
        if not label:
            return

        if is_selected:
            label.setStyleSheet(
                "border: 2px solid #5865f2; background-color: rgba(88, 101, 242, 0.2);"
            )
        else:
            path = getattr(label, "file_path", getattr(label, "path", ""))
            is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
            if is_video:
                label.setStyleSheet(
                    "border: 2px solid #3498db; background-color: transparent;"
                )
            else:
                label.setStyleSheet(
                    "border: 1px solid #4f545c; background-color: transparent;"
                )

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
                    self.update_card_style(card, self.is_path_selected(path))
            except RuntimeError:
                pass

        reset_card(old_path, self.path_to_card_widget.get(old_path))

        if is_closing:
            sender_win = self.sender()
            if sender_win in self.open_preview_windows:
                self.open_preview_windows.remove(sender_win)
            return

        def highlight_card(path, card):
            if not card or not path:
                return
            try:
                self.update_card_style(card, self.is_path_selected(path))
                if card.property("original_style") is None:
                    card.setProperty("original_style", card.styleSheet())
                current = card.styleSheet().strip()
                sep = "" if not current or current.endswith(";") else ";"
                card.setStyleSheet(f"{current}{sep} border: 4px solid #3498db;")
            except RuntimeError:
                pass

        highlight_card(new_path, self.path_to_card_widget.get(new_path))

    def create_card_widget(self, path: str, pixmap: Optional[QPixmap]) -> QWidget:
        container = QWidget()
        container.setFixedSize(self.approx_item_width, self.approx_item_width)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setAlignment(Qt.AlignCenter)

        # Factory method
        label = self.create_gallery_label(path, self.thumbnail_size)
        # label.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent) # Removed to fix artifacts

        # Initial State
        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))

        if (pixmap and not pixmap.isNull()) or (
            hasattr(self, "_failed_paths") and path in self._failed_paths
        ):
            self.update_card_pixmap(container, pixmap, label_ref=label)
        else:
            # Default "Loading..." State
            label.clear()
            label.setText("Loading...")
            if is_video:
                label.setStyleSheet(
                    "border: 2px solid #3498db; color: #3498db; "
                    "font-weight: bold; background-color: #2c2f33;"
                )
            else:
                label.setStyleSheet(
                    "border: 1px dashed #666; color: #888; "
                    "font-size: 10px; background-color: #2c2f33;"
                )

        layout.addWidget(label)

        # Apply Initial Style
        is_selected = path in self.selected_files
        self.update_card_style(container, is_selected)

        return container

    def update_card_pixmap(
        self,
        widget: QWidget,
        pixmap: Optional[QPixmap],
        label_ref: Optional[QLabel] = None,
    ):
        label = label_ref if label_ref is not None else widget.findChild(QLabel)

        if not label:
            return

        # Resolve 'path' vs 'file_path' attribute inconsistency between different Label classes
        path = getattr(label, "file_path", getattr(label, "path", ""))
        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))

        # 1. Check Failure State
        # 1. Check Failure State
        if hasattr(self, "_failed_paths") and path in self._failed_paths:
            label.clear()
            label.setScaledContents(False)

            if is_video:
                # Match ImageExtractorTab style ("VIDEO" text, Blue border)
                label.setText("VIDEO")
                label.setStyleSheet(
                    "border: 2px solid #3498db; color: #3498db; font-weight: bold; background-color: #2c2f33;"
                )
            else:
                label.setText("No Thumbnail")
                label.setStyleSheet(
                    "border: 2px solid #e74c3c; color: #e74c3c; font-weight: bold; background-color: #2c2f33;"
                )

            label.show()
            return

        # 2. Check Success State
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                self.thumbnail_size,
                self.thumbnail_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            label.setPixmap(scaled)
            label.setText("")

            if is_video:
                label.setStyleSheet(
                    "border: 2px solid #3498db; background-color: transparent;"
                )
            else:
                label.setStyleSheet(
                    "border: 1px solid #4f545c; background-color: transparent;"
                )

        # 3. Loading/Empty State
        else:
            label.setText("Load Failed")
            label.setStyleSheet(
                "border: 1px solid #e74c3c; color: #e74c3c; font-size: 10px; background-color: #2c2f33;"
            )

    def _generate_video_thumbnail(self, path: str) -> Optional[QPixmap]:
        """
        Generates a video thumbnail synchronously on demand.
        Used for fallback or when immediate preview is needed.
        """
        try:
            # 1. Check disk cache first
            cache_path = self._get_disk_cache_path(path)
            if os.path.exists(cache_path):
                img = QImage(cache_path)
                if not img.isNull():
                    return QPixmap.fromImage(img)

            # 2. Generate new
            thumbnailer = VideoThumbnailer()
            image = thumbnailer.generate(path, self.thumbnail_size)
            if image and not image.isNull():
                # 3. Save to disk cache
                image.save(cache_path, "JPG")
                return QPixmap.fromImage(image)
        except Exception as e:
            print(f"Failed to generate explicit video thumbnail for {path}: {e}")
        return None

    # --- PAGINATION UI HELPERS ---

    def create_pagination_controls(self) -> QWidget:
        """Uses shared logic to create UI, then binds signals."""
        container, controls = self.common_create_pagination_ui()

        # Bind Controls
        self.page_combo = controls["combo"]
        self.prev_btn = controls["btn_prev"]
        self.next_btn = controls["btn_next"]
        self.page_button = controls["btn_page"]
        self.item_range_lbl = controls["item_range_lbl"]
        self.thumb_slider = controls["thumb_slider"]
        self.thumb_size_lbl = controls["thumb_size_lbl"]

        # Signal Connections
        self.page_combo.currentTextChanged.connect(self._on_page_size_changed)
        self.prev_btn.clicked.connect(lambda: self._change_page(-1))
        self.next_btn.clicked.connect(lambda: self._change_page(1))

        # §4.11 — thumbnail slider
        self.thumb_slider.setValue(self.thumbnail_size)
        self.thumb_size_lbl.setText(f"{self.thumbnail_size} px")
        self.thumb_slider.valueChanged.connect(self._on_thumb_slider_changed)
        self.thumb_slider.sliderReleased.connect(self._save_thumbnail_size)

        # §2.13A — sort controls
        sc = controls["sort_combo"]
        sd = controls["sort_dir_btn"]
        self.sort_combo = sc
        self.sort_dir_btn = sd
        sc.currentTextChanged.connect(self._on_sort_combo_changed)
        sd.clicked.connect(lambda: self._on_sort_dir_toggled(sd))

        # Initial UI update
        self._update_pagination_ui()

        return container

    def _on_page_size_changed(self, text: str):
        size = 999999 if text == "All" else int(text)
        self.page_size = size
        self.current_page = 0
        self.refresh_gallery_view()

    def _on_thumb_slider_changed(self, value: int) -> None:
        """Live thumbnail resize via slider (§4.11)."""
        snapped = max(64, min(512, (value // 16) * 16))
        if snapped == self.thumbnail_size:
            return
        self.thumbnail_size = snapped
        self.approx_item_width = snapped + self.padding_width + 20
        self._sync_thumb_slider()
        self._on_layout_change()
        paths = self.common_get_paginated_slice(
            self.master_image_paths, self.current_page, self.page_size
        )
        if paths:
            self.start_loading_gallery(paths)

    def _change_page(self, delta: int):
        total_items = len(self.gallery_image_paths)
        if total_items == 0:
            return

        max_page = math.ceil(total_items / self.page_size) - 1
        new_page = max(0, min(self.current_page + delta, max_page))

        if new_page != self.current_page:
            self.current_page = new_page
            self.refresh_gallery_view()

    def _jump_to_page(self, page_index: int):
        if page_index != self.current_page:
            self.current_page = page_index
            self.refresh_gallery_view()

    def _update_pagination_ui(self):
        if not hasattr(self, "page_button"):
            return

        controls = {
            "btn_page": self.page_button,
            "btn_prev": self.prev_btn,
            "btn_next": self.next_btn,
        }

        total = len(self.gallery_image_paths)

        # Use shared logic
        corrected_page, total_pages = self.common_update_pagination_state(
            total, self.page_size, self.current_page, controls
        )
        self.current_page = corrected_page

        # §3.9 — update item range label
        if hasattr(self, "item_range_lbl"):
            if total == 0:
                self.item_range_lbl.setText("0 images")
            else:
                first = corrected_page * self.page_size + 1
                last = min(first + self.page_size - 1, total)
                self.item_range_lbl.setText(f"Items {first}–{last} of {total}")

        # --- FIX: Prevent memory leak and crash by deleting the old menu safely ---
        old_menu = self.page_button.menu()
        if old_menu:
            old_menu.deleteLater()

        # Update Menu
        menu = QMenu(self)
        for i in range(total_pages):
            page_num = i + 1
            action = QAction(f"Page {page_num}", menu)  # Parent to menu instead of self
            action.setCheckable(True)
            action.setChecked(i == self.current_page)
            # Use a slightly safer way to connect signals to avoid capturing by reference issues
            action.triggered.connect(lambda checked=False, p=i: self._jump_to_page(p))
            menu.addAction(action)
        self.page_button.setMenu(menu)

    # --- GEOMETRY & EVENTS ---

    def resizeEvent(self, event: QResizeEvent):
        QWidget.resizeEvent(self, event)
        self._resize_timer.start(100)

    def showEvent(self, event):
        super().showEvent(event)
        self._on_layout_change()

    @Slot()
    def _on_layout_change(self):
        self._connect_scroll_zoom()
        if self.gallery_scroll_area and self.gallery_layout:
            # Shared Calculation
            new_cols = self.common_calculate_columns(
                self.gallery_scroll_area, self.approx_item_width
            )

            if new_cols != self._current_cols:
                self._current_cols = new_cols
                # Shared Reflow
                self.common_reflow_layout(self.gallery_layout, new_cols)

    def _perform_search(self):
        query = self.search_input.text()
        filtered = self.common_filter_string_list(self.master_image_paths, query)
        self.gallery_image_paths = filtered
        self.current_page = 0
        self.refresh_gallery_view()

    # --- LOADING LOGIC ---

    def closeEvent(self, event):
        """Cleanup processes on close."""
        self.cancel_loading()
        super().closeEvent(event)

    @Slot(list, list)
    def _on_batch_images_loaded(self, results: List[tuple], requested_paths: List[str]):
        # Cleanup worker reference if called from signals
        sender = self.sender()
        if sender:
            # We need to find the worker that owns this signals object
            for worker in list(self._active_workers):
                if worker.signals == sender:
                    self._active_workers.remove(worker)
                    break

        # 1. Update Results
        for path, q_image in results:
            if path in self._loading_paths:
                self._loading_paths.remove(path)

            pixmap = QPixmap.fromImage(q_image)
            widget = self.path_to_card_widget.get(path)

            if not pixmap.isNull():
                if not q_image.isNull():
                    self._initial_pixmap_cache[path] = q_image  # store QImage
                if widget:
                    self.update_card_pixmap(widget, pixmap)
            else:
                # Mark as failed if the image is Null
                if not hasattr(self, "_failed_paths"):
                    self._failed_paths = set()
                self._failed_paths.add(path)
                if widget:
                    self.update_card_pixmap(widget, QPixmap())

        # 2. Cleanup Missing Results
        processed_paths = set(p for p, _ in results)
        for path in requested_paths:
            if path not in processed_paths:
                if path in self._loading_paths:
                    self._loading_paths.remove(path)

                if not hasattr(self, "_failed_paths"):
                    self._failed_paths = set()
                self._failed_paths.add(path)

                widget = self.path_to_card_widget.get(path)
                if widget:
                    self.update_card_pixmap(widget, QPixmap())

    def _trigger_batch_video_load(self, paths: List[str]):
        # User requested parallel/out-of-order loading.
        # Spawning individual workers allows QThreadPool to manage concurrency.
        for path in paths:
            self._trigger_video_load(path)

    def _trigger_batch_found_load(self, paths: List[str]):
        if not hasattr(self, "_loading_paths"):
            self._loading_paths = set()
        self._loading_paths.update(paths)
        worker = BatchImageLoaderWorker(paths, self.thumbnail_size)
        worker.signals.result.connect(self._on_single_image_loaded)
        worker.signals.batch_result.connect(self._on_batch_images_loaded)

        self._active_workers.add(worker)
        self.thread_pool.start(worker)

    def _trigger_video_load(self, path: str):
        self._loading_paths.add(path)
        worker = VideoLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(
            self._on_single_image_loaded
        )  # Reuse same handler
        self.thread_pool.start(worker)

    def start_loading_gallery(
        self,
        paths: List[str],
        show_progress: bool = True,
        append: bool = False,
        pixmap_cache: Optional[Dict[str, QPixmap]] = None,
    ):
        """
        Starts the loading process. Accepts an optional pixmap_cache for pre-generated thumbnails.
        """
        if not append:
            self.master_image_paths = self._apply_sort(list(paths))
            self._perform_search()

            self._initial_pixmap_cache = LRUImageCache(maxsize=300)
            if pixmap_cache:
                for k, v in pixmap_cache.items():
                    self._initial_pixmap_cache[k] = v
            self._loading_paths.clear()
            self._failed_paths.clear()
        else:
            self.master_image_paths.extend(paths)
            self.master_image_paths.sort(key=natural_sort_key)
            if pixmap_cache and pixmap_cache is not self._initial_pixmap_cache:
                for k, v in pixmap_cache.items():
                    self._initial_pixmap_cache[k] = v
            # Re-apply search to include new appended items
            self._perform_search()

        # self.refresh_gallery_view() # _perform_search calls this

    def refresh_gallery_view(self):
        self.cancel_loading()
        self.clear_gallery_widgets()
        self._update_pagination_ui()

        if not self.gallery_image_paths:
            self.common_show_placeholder(
                self.gallery_layout, "No images to display.", self.calculate_columns()
            )
            return

        # Prepare for sequential loading
        self._paginated_paths = self.common_get_paginated_slice(
            self.gallery_image_paths, self.current_page, self.page_size
        )
        self._populating_index = 0

        # Start population
        self._populate_step()

    def _populate_step(self):
        """Adds a small batch of widgets to the layout."""
        if not hasattr(self, "_paginated_paths") or self._populating_index >= len(
            self._paginated_paths
        ):
            self._load_all_page_images()
            return

        cols = self.calculate_columns()
        batch_size = 5
        limit = min(self._populating_index + batch_size, len(self._paginated_paths))

        for i in range(self._populating_index, limit):
            path = self._paginated_paths[i]
            _cached = self._initial_pixmap_cache.get(path)

            # 2. Check for Video if no cache exists
            is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
            if _cached is None and is_video:
                cache_path = self._get_disk_cache_path(path)
                if os.path.exists(cache_path):
                    _cached = QImage(cache_path)
                    if not _cached.isNull():
                        self._initial_pixmap_cache[path] = _cached

            initial_pixmap = (
                QPixmap.fromImage(_cached) if isinstance(_cached, QImage) else _cached
            )

            # 3. Create Widget
            card = self.create_card_widget(path, initial_pixmap)
            self._add_filename_label(card, path)  # §2.14A
            self.path_to_card_widget[path] = card

            # 4. Add to Layout
            row = i // cols
            col = i % cols
            if self.gallery_layout:
                self.gallery_layout.addWidget(
                    card, row, col, Qt.AlignLeft | Qt.AlignTop
                )

            # 5. DEFER Async Load (Visibility Check)
            # Both images and videos are now loaded asynchronously via visibility check
            # if initial_pixmap is None:
            #     pass

        self._populating_index = limit

        if self._populating_index < len(self._paginated_paths):
            self._populate_timer.start(0)
        else:
            self._load_all_page_images()

    def _load_all_page_images(self):
        """Triggers loading for all images in the current paginated view."""
        if not self._paginated_paths:
            return

        paths_to_load = []
        for path in self._paginated_paths:
            if path in self._initial_pixmap_cache:
                continue
            if path in self._loading_paths:
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
                self._trigger_video_load(p)

        if image_paths:
            self._trigger_batch_found_load(image_paths)

    def calculate_columns(self):
        return self.common_calculate_columns(
            self.gallery_scroll_area, self.approx_item_width
        )

    def _trigger_image_load(self, path: str):
        self._loading_paths.add(path)
        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.signals.result.connect(self._on_single_image_loaded)

        self._active_workers.add(worker)
        self.thread_pool.start(worker)

    @Slot(str, QImage)
    def _on_single_image_loaded(self, path: str, q_image: QImage):
        # Cleanup worker ref
        sender = self.sender()
        if sender:
            # We need to find the worker that owns this signals object
            for worker in list(self._active_workers):
                if worker.signals == sender:
                    self._active_workers.remove(worker)
                    break

        if path in self._loading_paths:
            self._loading_paths.remove(path)

        pixmap = QPixmap.fromImage(q_image)

        # If loading failed, mark as failed instead of generating a red placeholder
        if pixmap.isNull():
            if not hasattr(self, "_failed_paths"):
                self._failed_paths = set()
            self._failed_paths.add(path)

            # Cache a null sentinel so _load_all_page_images stops requesting this path
            self._initial_pixmap_cache[path] = QImage()

            widget = self.path_to_card_widget.get(path)
            if widget:
                # This will trigger the "VIDEO" / "No Thumbnail" text style via update_card_pixmap
                self.update_card_pixmap(widget, QPixmap())
            return

        # Cache the raw QImage (half the RAM of QPixmap on X11)
        if not q_image.isNull():
            self._initial_pixmap_cache[path] = q_image

            # Save to disk cache if it's a video
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                cache_path = self._get_disk_cache_path(path)
                if not os.path.exists(cache_path):
                    q_image.save(cache_path, "JPG")

        widget = self.path_to_card_widget.get(path)
        if widget:
            self.update_card_pixmap(widget, pixmap)

    def _generate_error_pixmap(self) -> QPixmap:
        """Generates a visual placeholder for failed loads."""
        size = self.thumbnail_size
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor("#2c2f33"))

        painter = QPainter(pixmap)
        # Red border
        painter.setPen(QColor("#e74c3c"))
        painter.drawRect(0, 0, size - 1, size - 1)

        # Text
        painter.setPen(QColor("#e74c3c"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "No Thumbnail")
        painter.end()

        return pixmap

    # --- HELPERS ---

    def cancel_loading(self):
        """Stops all active timers and background workers."""
        if self._populate_timer.isActive():
            self._populate_timer.stop()
        if self._resize_timer.isActive():
            self._resize_timer.stop()
        if (
            hasattr(self, "search_debounce_timer")
            and self.search_debounce_timer.isActive()
        ):
            self.search_debounce_timer.stop()

        # Stop all active workers
        for worker in list(self._active_workers):
            try:
                worker.stop()
            except Exception:
                pass
        self._active_workers.clear()

        if hasattr(self, "thread_pool"):
            self.thread_pool.clear()

        # CRITICAL FIX: Clear loading paths so interrupted loads don't block future attempts
        self._loading_paths.clear()
        if hasattr(self, "found_loading_paths"):
            self.found_loading_paths.clear()

    def clear_gallery_widgets(self):
        self.cancel_loading()
        self.path_to_card_widget.clear()
        self._paginated_paths = []

        if not self.gallery_layout:
            return
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
